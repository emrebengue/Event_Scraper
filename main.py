import os
import re
import time
import requests
from collections import defaultdict
#from collections import Counter
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def is_dynamic(url):
    """Determine if a webpage is dynamic or static based on JavaScript usage."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        html = response.text.lower()

        if re.search(r"<script[^>]*>.*?</script>", html, re.DOTALL) or "xmlhttprequest" in html:
            return True
        return False
    except Exception as e:
        print(f"Error detecting website type: {e}")
        return False


def setup_directories(url):
    """Create a structured directory for storing extracted data."""
    parsed_url = urlparse(url)
    domain_parts = parsed_url.netloc.split(".")

    # Handle subdomains properly (e.g., "iacac.knack.com" → "iacac.knack")
    domain = ".".join(
        domain_parts[-3:]) if len(domain_parts) > 2 else ".".join(domain_parts)

    today = datetime.today().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%H:%M')

    base_dir = os.path.join(os.getcwd(), domain, f"{today}")
    # base_dir = os.path.join(os.getcwd(), domain)
    os.makedirs(base_dir, exist_ok=True)

    return base_dir


def save_html(html, path):
    """Save HTML content to a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(html)


def save_screenshot(driver, path):
    """Take a full-page screenshot using JavaScript to scroll."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    total_height = driver.execute_script("return document.body.scrollHeight")

    # Set height
    driver.set_window_size(1920, total_height)

    time.sleep(2)
    driver.save_screenshot(path)

# Selenium driver initialization
def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-cache")
    options.add_argument("--disk-cache-size=0")
    options.add_argument("--disable-application-cache")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/58.0.3029.110 Safari/537.3"
    )
    driver = webdriver.Chrome(options=options)
    return driver


def scrape_static(url, is_main_url):
    """Scrape a static webpage and return clean HTML body content."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            if is_main_url:
                return extract_event_sections(response.text)
            else:
                return extract_date_location_sections(response.text)
        print(f"Failed to fetch static page: {response.status_code}")
        return None
    except Exception as e:
        print(f"Error scraping static site: {e}")
        return None


def scrape_dynamic(url, save_dir, is_main_url):
    """Use Selenium to scrape dynamic websites, extract clean HTML body, and take a full-page screenshot."""
    try:

        driver = init_driver()

        driver.get(url)
        time.sleep(3)

        # driver.execute_script("location.reload();")
        # driver.refresh()

        # Wait for body to fully load
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")

        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)


        # To not override first png
        place_holder = datetime.now().strftime("%H%M%S")
        print(f"Selenium is using: {driver.current_url}")


        screenshot_path = os.path.join(save_dir, f"{place_holder}.png")
        save_screenshot(driver, screenshot_path)

        text = driver.page_source
        driver.quit()

        # Extract clean <body> content
        if is_main_url:
            html_body = extract_event_sections(text)
        else:
            html_body = extract_date_location_sections(text)
        # return html_body, screenshot_path
        return html_body, screenshot_path

    except Exception as e:
        print(f"Error scraping dynamic site: {e}")
        return None, None


def extract_event_sections(html_text):
    """
    Given raw HTML text, this function parses and cleans the HTML,
    then uses a weighted scoring system to identify which container
    most likely holds event information. We boost candidates that contain
    both date and time information.
    """
    # Parse and clean HTML
    soup = BeautifulSoup(html_text, 'html.parser')
    # Remove irrelevant tags
    for tag in soup(['script', 'style', 'img', 'link', 'footer', 'header', 'nav']):
        tag.decompose()

    # Keywords Section (regex)
    event_keywords = {
        'terms': r'\b(calendar|schedule|event|fair|seminar|webinar|workshop|session|day|college|hub|club|group|meeting|high school|career|prep|hs|conference|expo|symposium)\b',
        'class_ids': r'calendar|schedule|events?|program',
        # Date formats: matches common numeric dates and month name dates.
        'date_formats': r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2})\b',
        # Time formats: e.g., 1:00 PM, 09:30 am, etc.
        'time_formats': r'\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\b',
        'schema_org': r'schema\.org/Event'
    }

    # Check for schema.org
    schema_events = soup.find_all(
        attrs={"itemtype": "http://schema.org/Event"})
    if schema_events:
        return '\n'.join([str(e.parent.parent) for e in schema_events])

    candidates = []
    elements = soup.find_all(
        ['div', 'section', 'article', 'li', 'tr', 'tbody'])
    for element in elements:
        score = 0
        # Get all text with some whitespace separation
        element_text = element.get_text(separator=' ', strip=True).lower()
        attributes = ' '.join([str(element.attrs)]).lower()

        # detect Schema.org
        if re.search(event_keywords['schema_org'], attributes):
            score += 4

        # Keyword matching in element text
        if re.search(event_keywords['terms'], element_text, flags=re.IGNORECASE):
            score += 3

        # Keyword matching in class/id attributes
        class_list = element.get('class', [])
        element_class = ' '.join(class_list) if class_list else ''
        element_id = element.get('id', '')
        class_id = f"{element_class} {element_id}".strip()
        if re.search(event_keywords['class_ids'], class_id, re.IGNORECASE):
            score += 2

        # detect date-time and boost
        date_found = re.search(event_keywords['date_formats'], element_text)
        time_found = re.search(event_keywords['time_formats'], element_text)
        if date_found and time_found:
            score += 4  # Strong indicator when both are found
        elif date_found:
            score += 2
        elif time_found:
            score += 1

        # boost list/table items.
        if element.name in ['li', 'tr']:
            score += 1
        if element.find_parent(['ul', 'ol', 'table']):
            score += 1

        if score > 0:
            candidates.append((element, score))

    # Aggregate scores up the DOM tree so that a parent that contains many candidates gets a boost.
    container_scores = defaultdict(int)
    for element, score in candidates:
        # Look upward to parents (limit to three levels) and sum their scores.
        parents = element.find_parents(['div', 'section', 'article'], limit=3)
        for parent in parents:
            container_scores[parent] += score

    if not container_scores:
        return "No event section found"

    # Choose the container with the highest score.
    best_container = max(container_scores.items(), key=lambda x: x[1])[0]
    return str(best_container.prettify())
    # return best_container


def extract_date_location_sections(html_text):
    """
    Extracts sections of HTML containing date, time, and location information,
    then moves up two parent levels to return the relevant event section.
    """
    # Parse HTML
    soup = BeautifulSoup(html_text, 'html.parser')

    # Remove unnecessary tags
    for tag in soup(['script', 'style', 'img', 'link', 'footer', 'header', 'nav']):
        tag.decompose()

    # Regular expressions for identifying date, time, and location patterns
    patterns = {
        'date': r"\b((?:Mon|Tues|Wed(?:nes)?|Thu(?:rs)?|Fri|Sat|Sun)(?:day)?,?\s*)?"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)(?:\.|,)?\s+\d{1,2}(?:st|nd|rd|th)?\,?\s*(?:\d{4})?"
        r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        'time': r"\b\d{1,2}:\d{2}\s*(?:[AaPp]\.?[Mm]\.?)?\s*(?:-|to)\s*\d{1,2}:\d{2}"
        r"\s*(?:[AaPp]\.?[Mm]\.?)?\b|\b\d{1,2}:\d{2}\s*(?:[AaPp]\.?[Mm]\.?)?\b",
        'location': r"\b([A-Z][a-z]+(?:[ -][A-Z][a-z]+)*,\s*(?:[A-Z]{2}|(?:Alabama|Alaska|Arizona|"
        r"Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|"
        r"Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|"
        r"Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|"
        r"New\sHampshire|New\sJersey|New\sMexico|New\sYork|North\sCarolina|North\sDakota|"
        r"Ohio|Oklahoma|Oregon|Pennsylvania|Rhode\sIsland|South\sCarolina|South\sDakota|"
        r"Tennessee|Texas|Utah|Vermont|Virginia|Washington|West\sVirginia|Wisconsin|Wyoming))"
        r"|(?:High\s+School|University|College|Campus|Institute))\b"
    }
    # Search for elements that contain date, time, or location
    candidates = []
    elements = soup.find_all(
        ['div', 'section', 'article', 'li', 'tr', 'tbody', 'p'])

    for element in elements:
        score = 0
        element_text = element.get_text(separator=' ', strip=True).lower()

        # Check for date, time, and location keywords
        date_found = re.search(
            patterns['date'], element_text, flags=re.IGNORECASE)
        time_found = re.search(
            patterns['time'], element_text, flags=re.IGNORECASE)
        location_found = re.search(
            patterns['location'], element_text, flags=re.IGNORECASE)

        if date_found:
            score += 3
        if time_found:
            score += 2
        if location_found:
            score += 3

        # Boost score if multiple factors are found
        if date_found and location_found:
            score += 4
        if date_found and time_found:
            score += 3
        if date_found and time_found and location_found:
            score += 6  # Strong indication of event info

        if score > 0:
            candidates.append((element, score))

    if not candidates:
        return "No date or location information found"

    # Aggregate scores for parents
    container_scores = defaultdict(int)
    for element, score in candidates:
        parents = element.find_parents(
            ['section', 'article', 'tbody', 'tr'], limit=2)
        for parent in parents:
            container_scores[parent] += score

    if not container_scores:
        return "No relevant container found"

    # Choose the best container
    best_container = max(container_scores.items(), key=lambda x: x[1])[0]

    # return str(best_container.prettify())

    # NARROW DOWN FROM HERE

    refined_candidates = []
    for child in best_container.find_all(['p', 'span', 'strong', 'li', 'div'], recursive=True):
        child_text = child.get_text(separator=' ', strip=True).lower()
        if (
            re.search(patterns['date'], child_text, flags=re.IGNORECASE) or
            re.search(patterns['time'], child_text, flags=re.IGNORECASE) or
            re.search(patterns['location'], child_text, flags=re.IGNORECASE)
        ):
            refined_candidates.append(child)

    # Select the smallest tag that contains all required info
    best_final_container = None
    for candidate in refined_candidates:
        candidate_text = candidate.get_text(separator=' ', strip=True).lower()
        if (
            re.search(patterns['date'], candidate_text, flags=re.IGNORECASE) and
            re.search(patterns['time'], candidate_text, flags=re.IGNORECASE) and
            re.search(patterns['location'], candidate_text, flags=re.IGNORECASE)):
            best_final_container = candidate
            break  # Stop once we find the best match

    if best_final_container:
        best_container = best_final_container

    if best_container.parent and best_container.parent.name is not ['html', 'body']:
        best_container = best_container.parent

    # for _ in range(2):
    #     if best_container.parent and best_container.parent.name is not ['html', 'body']:
    #         best_container = best_container.parent

    # Remove irrelevant nested elements
    for tag in best_container(['button', 'script', 'style', 'img', 'svg', 'form', 'footer', 'header', 'nav']):
        tag.decompose()

    return str(best_container.prettify())


def extract_event_links(html, base_url):
    """Extract event links from the webpage and convert them into absolute URLs."""
    soup = BeautifulSoup(html, "html.parser")
    event_links = set()
    terms = re.compile(
        r'\b(calendar|schedule|event|fair|seminar|webinar|workshop|session|day|college|hub|club|group|meeting|high school|career|prep|hs|conference|expo|symposium)\b')

    for link in soup.find_all('a', href=True):
        href = link['href'].strip()
        link_text = link.get_text(strip=True)
        # Ensure it's a valid link
        if not href or href.startswith("javascript") or href == "#":
            continue

        # Convert relative URLs to absolute URLs using urljoin
        if not href.startswith("http"):
            full_url = urljoin(base_url, href)
        else:
            full_url = href  # Already an absolute URL

        # Check if the link or its text contains event-related keywords
        if terms.search(full_url) or terms.search(link_text):
            event_links.add(full_url)

    return list(event_links)


def url_name_parser(url):
    parsed_url = urlparse(url)
    domain_parts = parsed_url.netloc.split(".")
    event_name = ".".join(
        domain_parts[-3:]) if len(domain_parts) > 2 else ".".join(domain_parts)

    return event_name

# SCRAPE EVENTS PART AND SAVE SCREENSHOT


def process_event_page(count, url, save_dir, is_main_function):
    """Scrape an event page, save its HTML body, and take a screenshot."""

    event_name = url_name_parser(url)

    # today = datetime.today().strftime('%Y-%m-%d')
    # timestamp = datetime.now().strftime('%H:%M')

    # event_dir = os.path.join(save_dir, today, event_name)
    # os.makedirs(event_dir, exist_ok=True)

    if is_dynamic(url):
        html_body, screenshot_path = scrape_dynamic(
            url, save_dir, is_main_function)
    else:
        html_body = scrape_static(url, is_main_function)
        screenshot_path = None  # Static pages don't need a screenshot

    if html_body:
        save_html(html_body, os.path.join(save_dir, f"{count+1}.html"))

    if screenshot_path:
        os.rename(screenshot_path, os.path.join(save_dir, f"{count+1}.png"))


def similarity_score(url1, url2):
    """Calculate similarity between two URLs based on shared path segments."""
    segments1 = url1.split("/")
    segments2 = url2.split("/")

    # Count matching segments from start
    match_count = sum(1 for a, b in zip(segments1, segments2) if a == b)

    return match_count


def cluster_links(links):
    """Cluster URLs based on structural similarity and return the most common group."""
    if not links:
        return []

    # Dictionary to track the most common patterns
    pattern_count = defaultdict(list)

    for i, url1 in enumerate(links):
        # Remove the last segment (ID-like part)
        pattern = "/".join(url1.split("/")[:-1])
        pattern_count[pattern].append(url1)

    # Find the most frequent pattern
    most_frequent_pattern = max(
        pattern_count, key=lambda k: len(pattern_count[k]), default=None)

    if most_frequent_pattern:
        return pattern_count[most_frequent_pattern]

    return links  # If no clear clustering, return all


def write_to_file(filename, text):
    """To write in a file"""
    with open(filename, "a", encoding="utf-8") as file:  # "a" mode appends to the file
        file.write(text + "\n")


def main(url):
    """Main function to crawl events, process pages, and store data."""
    save_dir = setup_directories(url)

    # THIS IS THE PARENT FOLDER
    main_dir = os.path.join(save_dir, os.pardir)

    is_main_function = True

    main_page = url_name_parser(url)

    # Scrape the main page
    if is_dynamic(url):
        main_html, screenshot_path = scrape_dynamic(
            url, save_dir, is_main_function)
        os.rename(screenshot_path, os.path.join(save_dir, f"{main_page}.png"))
    else:
        main_html = scrape_static(url, is_main_function)
        screenshot_path = None  # No screenshot for static pages

    is_main_function = False

    if not main_html:
        # print(f"Failed to retrieve {url}")
        return

    # DEBUG
    # print("this is main_html:",main_html)

    # Save extracted HTML
    save_html(main_html, os.path.join(save_dir, f"{main_page}.html"))

    # Rename so it does not get overwritten
    # if screenshot_path:
    #     os.rename(screenshot_path, os.path.join(save_dir, f"{main_page}.png"))

    # Extract event links
    event_links = extract_event_links(main_html, url)

    # print(f"These are the event links for {main_page}:", event_links)

    unique_links = cluster_links(event_links)
    if url in unique_links:
        unique_links.remove(url)
    # #print("len of unique links",len(unique_links))
    # #print("EVENT_LINKS", event_links)
    # for link in unique_links:
    #     print(link)
    # #print(f" Found {len(event_links)} event(s)")
    write_to_file("tacac_links_output.txt",f"There are {len(unique_links)}: \n {unique_links} \n")
    for counter, event_url in enumerate(unique_links):
        # print(f"[INFO] Processing event: {event_url}")
        process_event_page(counter, event_url, save_dir, is_main_function)


# start_url = "https://iacac.knack.com/college-fairs#list"
# start_url = "https://members.sacac.org/event-calendar"
# start_url = "https://www.pacac.org/event-calendar"
start_url = "https://www.tacac.org/college-fair-events"
# start_url = "https://www.njacac.org/"
main(start_url)

# url_list = ["https://iacac.knack.com/college-fairs#list", "https://members.sacac.org/event-calendar","https://www.tacac.org/college-fair-events", "https://www.pacac.org/event-calendar", "https://www.njacac.org/" ]

# for url in url_list:
#     main(url)
