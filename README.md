# Event_Scraper
Honours  Project - Emirali Gungor, Emre Bengu

## Overview

This project aims to scrape event pages from various US school fair websites and extract structured information such as event dates, times, locations, and event-related links. The scraper currently requires a direct URL to the events page (not the homepage) since it does not yet implement a web crawler. The extracted data is stored in an organized directory structure, including both HTML content and screenshots.

## Thought Process

When we started the project, we analyzed multiple websites (provided by our client) to determine if they loaded dynamically or statically. We quickly realized that almost all tested websites were dynamic, meaning their event information was loaded via JavaScript rather than being available in the initial HTML response. This led us to choose Selenium along with BeautifulSoup for scraping, as it allows us to render JavaScript and extract the dynamically loaded content.

Next, we needed a method to accurately identify the event information section within a given website. We devised a weighted system based on event-related keywords, structured elements, and metadata such as schema.org annotations. This system helps us extract event-related sections even when websites structure their HTML differently. The function `extract_event_sections` was implemented for this purpose.

During our tests, we observed that many event pages did not contain event details directly but instead provided links to individual event pages. This required us to extract all links from the identified event section and filter them to retain only relevant event pages. Initially, we experimented with multiple regex-based filtering techniques, but due to variations in website structures, it was difficult to standardize a universal regex pattern. As a result, we implemented the `cluster_links` function, which groups URLs based on common structural patterns. However, since this method does not eliminate all irrelevant links, we plan to incorporate an LLM to refine the filtering process while minimizing token usage to reduce costs.

Once we obtained the relevant event page links, we needed another function to extract event details such as date, time, and location. The `extract_date_location_sections` function was developed for this purpose. It first parses the HTML and removes irrelevant tags like scripts and images. Then, it scans for date, time, and location patterns using regex. When a match is found, it assigns a weighted score based on the presence of these elements. Unlike `extract_event_sections`, which focuses on broader event containers, this function moves up the DOM hierarchy to ensure the extracted information is complete and relevant. If multiple candidates are found, it selects the one with the highest score. This approach ensures we retrieve structured event details even from inconsistent HTML structures.

Finally, recognizing that some event details might be embedded in images, we implemented a directory system to store both HTML data and full-page screenshots. This allows us to perform OCR-based text extraction later if needed.

## Features

- **Dynamic and Static Website Handling**: Determines if a website loads dynamically or statically and scrapes it accordingly using Selenium (for dynamic sites) or Requests & BeautifulSoup (for static sites).
    
- **Event Section Identification**: Uses a weighted scoring system based on keywords, HTML structures, and schema.org event tags to extract event-related sections.
    
- **Event Link Extraction & Filtering**: Extracts event links from the identified event section and filters them using clustering techniques to remove unrelated links.
    
- **Date, Time, and Location Extraction**: Identifies event details and moves up the DOM tree to extract the relevant section.
    
- **Data Storage & Screenshots**: Saves extracted HTML, filtered event links, and full-page screenshots for future reference and OCR-based text extraction.
    

## Constraints

- The provided URL must be the events page (not the homepage) because a site-wide crawler is not yet implemented.
    
- Many school fair websites load events dynamically, requiring Selenium for JavaScript execution.
    
- Some websites list events as links rather than inline details, requiring an additional step to visit and scrape these links.
    
- Regex-based link filtering is difficult due to the variety of website structures, so an LLM will be used for final filtering to minimize token costs.
    

## Implementation Details

### 1. Identifying Website Type (Dynamic vs. Static)

The function `is_dynamic(url)` checks if the webpage contains JavaScript-related elements such as `<script>` tags and `XMLHttpRequest`, indicating a dynamic page.

### 2. Directory Structure Setup

The `setup_directories(url)` function creates structured directories based on the domain name and current date to store extracted HTML and screenshots.

### 3. Web Scraping

- **Static Pages:** `scrape_static(url, is_main_url)` fetches the HTML content using `requests.get()`.
    
- **Dynamic Pages:** `scrape_dynamic(url, save_dir, is_main_url)` uses Selenium to render JavaScript, scroll the page, and take a screenshot before extracting the page source.
    

### 4. Extracting Event Sections

The `extract_event_sections(html_text)` function:

- Parses HTML using BeautifulSoup.
    
- Removes irrelevant tags (`script`, `style`, `img`, etc.).
    
- Uses a weighted scoring system to identify event-related containers based on:
    
    - Presence of event-related keywords (calendar, fair, conference, etc.).
        
    - Presence of dates and times.
        
    - Schema.org event metadata.
        
    - Structural elements (lists, tables, sections).
        
- Returns the highest-scoring container as the likely event section.
    

### 5. Extracting Event Links

The `extract_event_links(html, base_url)` function:

- Finds all `<a>` tags with `href` attributes.
    
- Converts relative URLs to absolute URLs.
    
- Filters links based on event-related keywords.
    
- Returns a list of potential event-related links.
    

### 6. Filtering Event Links

The `cluster_links(links)` function:

- Groups URLs based on structural similarity (ignoring dynamic ID-like segments).
    
- Returns the most frequently occurring URL pattern.
    

### 7. Extracting Date, Time, and Location

The `extract_date_location_sections(html_text)` function:

- Identifies date, time, and location-related content using regex.
    
- Scores sections based on relevance.
    
- Moves up the DOM tree to return the most complete event information.
    

### 8. Processing Individual Event Pages

The `process_event_page(count, url, save_dir, is_main_function)` function:

- Scrapes each event link.
    
- Saves the extracted HTML and screenshot.
    

### 9. Main Execution Flow

The `main(url)` function:

1. Sets up the directory.
    
2. Scrapes the main event page.
    
3. Extracts and filters event links.
    
4. Visits each event link and extracts details.
    
5. Saves results to structured folders.

## Future Improvements

- Use an LLM to filter event links and sections more accurately while minimizing token usage.
    
- Implement OCR to extract text from screenshots when event details are embedded in images.
	
- Implement a crawler to find the events page automatically.
