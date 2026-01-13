#!/usr/bin/env python3
"""
GGGI Tender Scraper
Scrapes tender information from https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
Uses Selenium to render JavaScript and extract tender data.
Visits each tender's "View Details" page to extract full description.
Outputs results to a CSV file.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# URLs - Only scraping Current tenders as specified
BASE_URL = "https://in-tendhost.co.uk"
TENDERS_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Current"
PROJECT_DETAIL_URL = "https://in-tendhost.co.uk/gggi/aspx/ProjectManage"


def setup_driver():
    """Setup Chrome WebDriver with headless options."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        chrome_options.binary_location = "/usr/local/bin/google-chrome"
        driver = webdriver.Chrome(options=chrome_options)
    
    return driver


def clean_text(text):
    """Clean and normalize text."""
    if text is None:
        return ""
    text = re.sub(r'\s+', ' ', str(text).strip())
    return text


def wait_for_page_load(driver, timeout=60):
    """Wait for the tender page to fully load."""
    try:
        # First wait for page to start loading
        time.sleep(3)
        
        # Wait for container - with longer timeout
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "containerProjects"))
        )
        
        logger.info("Container found, waiting for AJAX content...")
        
        # Wait longer for AJAX content to load
        time.sleep(8)
        
        # Try to find tenders multiple times
        for attempt in range(10):
            elements = driver.find_elements(By.CSS_SELECTOR, "[data-timescalesid]")
            if elements:
                logger.info(f"Page loaded with {len(elements)} tenders after {attempt+1} attempts")
                return True
            logger.info(f"Waiting for tenders... attempt {attempt+1}")
            time.sleep(2)
        
        # Check page source for debugging
        page_source = driver.page_source
        if "data-timescalesid" in page_source:
            logger.info("Found timescalesid in page source")
            return True
        
        return True
    except TimeoutException:
        logger.warning("Timeout waiting for page to load")
        return True


def check_pagination(driver):
    """Check if there are more pages and return total page count."""
    try:
        # Look for pagination info like "Page 1 of 2"
        page_label = driver.find_element(By.ID, "labelPage")
        page_text = page_label.text
        match = re.search(r'(\d+)\s*of\s*(\d+)', page_text)
        if match:
            current_page = int(match.group(1))
            total_pages = int(match.group(2))
            return current_page, total_pages
    except:
        pass
    return 1, 1


def click_next_page(driver):
    """Click the next page button."""
    try:
        next_btn = driver.find_element(By.ID, "buttonNext")
        if next_btn.is_enabled():
            next_btn.click()
            time.sleep(3)
            return True
    except:
        pass
    return False


def extract_tenders_from_page(driver):
    """Extract tender information from the current page."""
    tenders = []
    
    try:
        tender_elements = driver.find_elements(By.CSS_SELECTOR, "[data-timescalesid]")
        logger.info(f"Found {len(tender_elements)} tender elements on current page")
        
        for elem in tender_elements:
            try:
                project_id = elem.get_attribute("data-timescalesid")
                
                # Skip if already processed (avoid duplicates)
                if any(t.get('project_id') == project_id for t in tenders):
                    continue
                
                # Extract title
                title = ""
                try:
                    header = elem.find_element(By.CSS_SELECTOR, ".box-header .font-14.bold")
                    title = clean_text(header.text)
                except NoSuchElementException:
                    try:
                        header = elem.find_element(By.CSS_SELECTOR, ".box-header")
                        title = clean_text(header.text.split('\n')[0])
                    except:
                        pass
                
                # Extract deadline
                deadline = ""
                try:
                    deadline_elem = elem.find_element(By.CSS_SELECTOR, ".box-header .text-right")
                    deadline_text = clean_text(deadline_elem.text)
                    if ":" in deadline_text:
                        deadline = deadline_text.split(":", 1)[1].strip()
                except:
                    pass
                
                tender_data = {
                    'project_id': project_id,
                    'title': title,
                    'reference': '',
                    'status': '',
                    'category': '',
                    'deadline': deadline,
                    'description': '',
                    'detail_url': f"{PROJECT_DETAIL_URL}/{project_id}" if project_id else '',
                }
                
                # Extract data from table rows
                try:
                    rows = elem.find_elements(By.CSS_SELECTOR, "table.table tr")
                    for row in rows:
                        try:
                            th = row.find_element(By.CSS_SELECTOR, "th label")
                            td = row.find_elements(By.CSS_SELECTOR, "td")
                            if th and td:
                                label = clean_text(th.text).lower().strip(':')
                                value = clean_text(td[-1].text) if td else ''
                                
                                if 'status' in label:
                                    tender_data['status'] = value
                                elif 'reference' in label:
                                    tender_data['reference'] = value
                                elif 'process' in label:
                                    tender_data['category'] = value
                                elif 'further information' in label:
                                    tender_data['further_information'] = value
                                elif 'title' in label and not tender_data['title']:
                                    tender_data['title'] = value
                        except:
                            continue
                except:
                    pass
                
                tenders.append(tender_data)
                
            except Exception as e:
                logger.warning(f"Error extracting tender: {e}")
                continue
        
    except Exception as e:
        logger.error(f"Error finding tender elements: {e}")
    
    return tenders


def visit_detail_page_and_extract_description(driver, tender):
    """
    Visit the tender's View Details page and extract the COMPLETE description.
    No truncation - gets all text from the Further Information field.
    """
    detail_url = tender.get('detail_url')
    if not detail_url:
        return tender
    
    logger.info(f"  -> Visiting View Details page: {detail_url}")
    
    try:
        driver.get(detail_url)
        time.sleep(3)  # Wait for page to load
        
        # Get page source and parse
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        description = ""
        
        # Method 1: Find "Further Information" field in tables - GET COMPLETE TEXT
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label_cell = cells[0]
                    value_cell = cells[-1]
                    
                    label = clean_text(label_cell.get_text()).lower().strip(':').strip()
                    
                    # For description fields, get the COMPLETE raw text without cleaning
                    if any(kw in label for kw in ['further information', 'description', 'summary', 'overview', 'details']):
                        # Get ALL text content - no truncation
                        raw_text = value_cell.get_text(separator=' ', strip=True)
                        # Only clean whitespace, keep all content
                        full_value = re.sub(r'\s+', ' ', raw_text).strip()
                        if len(full_value) > len(description):
                            description = full_value
                    else:
                        value = clean_text(value_cell.get_text())
                        # Extract other fields
                        if 'reference' in label and not tender.get('reference'):
                            tender['reference'] = value
                        elif 'status' in label and not tender.get('status'):
                            tender['status'] = value
                        elif ('category' in label or 'process' in label) and not tender.get('category'):
                            tender['category'] = value
                        elif ('publish' in label or 'issue date' in label) and not tender.get('published_date'):
                            tender['published_date'] = value
                        elif ('buyer' in label or 'organisation' in label) and not tender.get('buyer'):
                            tender['buyer'] = value
                        elif 'value' in label and not tender.get('value'):
                            tender['value'] = value
                        elif 'location' in label and not tender.get('location'):
                            tender['location'] = value
        
        # Method 2: Look for description in box-body tender divs - GET COMPLETE TEXT
        if not description or len(description) < 100:
            box_bodies = soup.find_all('div', class_='box-body')
            for box in box_bodies:
                if 'tender' in box.get('class', []):
                    # Get ALL text - no truncation
                    raw_text = box.get_text(separator=' ', strip=True)
                    full_text = re.sub(r'\s+', ' ', raw_text).strip()
                    if len(full_text) > 200:
                        if any(kw in full_text.lower() for kw in ['project', 'objective', 'scope', 'background', 'gggi', 'invit']):
                            if len(full_text) > len(description):
                                description = full_text
        
        # Method 3: Find main tender content area - GET COMPLETE TEXT
        if not description or len(description) < 100:
            tender_divs = soup.find_all('div', class_='tender')
            for div in tender_divs:
                raw_text = div.get_text(separator=' ', strip=True)
                full_text = re.sub(r'\s+', ' ', raw_text).strip()
                if len(full_text) > 200 and any(kw in full_text.lower() for kw in ['project', 'objective', 'consulting', 'scope']):
                    if len(full_text) > len(description):
                        description = full_text
        
        # Store COMPLETE description - NO TRUNCATION, NO BOILERPLATE REMOVAL
        # Keep everything as it appears on the page
        tender['description'] = description
        logger.info(f"  -> Extracted COMPLETE description: {len(description)} characters")
        
        # Extract document links
        doc_links = soup.find_all('a', href=re.compile(r'\.(pdf|doc|docx|xls|xlsx)', re.IGNORECASE))
        if doc_links:
            doc_names = [clean_text(link.get_text()) for link in doc_links if clean_text(link.get_text())]
            if doc_names:
                tender['documents'] = '; '.join(set(doc_names[:10]))
        
    except Exception as e:
        logger.warning(f"Error visiting detail page: {e}")
    
    return tender


def scrape_all_tenders():
    """Main function to scrape ALL tenders from the website."""
    logger.info("Starting GGGI Tender Scraper")
    logger.info(f"Target URL: {TENDERS_URL}")
    
    driver = setup_driver()
    all_tenders = []
    
    try:
        # Load the tenders page
        logger.info(f"\nLoading tenders page: {TENDERS_URL}")
        driver.get(TENDERS_URL)
        
        if not wait_for_page_load(driver):
            logger.error("Failed to load page")
            return []
        
        # Check pagination
        current_page, total_pages = check_pagination(driver)
        logger.info(f"Pagination: Page {current_page} of {total_pages}")
        
        # Collect all project IDs first to avoid duplicates
        collected_ids = set()
        
        # Scrape all pages
        page = 1
        while True:
            logger.info(f"\n--- Scraping Page {page} ---")
            
            # Extract tenders from current page
            page_tenders = extract_tenders_from_page(driver)
            
            # Add only new tenders (avoid duplicates)
            for tender in page_tenders:
                pid = tender.get('project_id')
                if pid and pid not in collected_ids:
                    collected_ids.add(pid)
                    all_tenders.append(tender)
            
            logger.info(f"Total unique tenders so far: {len(all_tenders)}")
            
            # Check if there are more pages
            _, total_pages = check_pagination(driver)
            if page >= total_pages:
                break
            
            # Try to go to next page
            if not click_next_page(driver):
                break
            
            page += 1
            time.sleep(2)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"TOTAL TENDERS FOUND: {len(all_tenders)}")
        logger.info(f"{'='*60}")
        
        # Now visit each tender's View Details page to get description
        if all_tenders:
            logger.info("\n" + "="*60)
            logger.info("VISITING EACH VIEW DETAILS PAGE TO EXTRACT DESCRIPTION")
            logger.info("="*60)
            
            for i, tender in enumerate(all_tenders):
                logger.info(f"\nProcessing {i + 1}/{len(all_tenders)}: {tender.get('title', 'Unknown')[:50]}")
                
                # Visit detail page and extract description
                updated_tender = visit_detail_page_and_extract_description(driver, tender)
                all_tenders[i] = updated_tender
                
                time.sleep(1)  # Be polite to server
        
    finally:
        driver.quit()
    
    return all_tenders


def save_to_csv(tenders, filename):
    """Save tender data to CSV file."""
    if not tenders:
        logger.warning("No tender data to save")
        return None
    
    # Column order with Description prominently placed
    columns = [
        'reference',
        'title',
        'status',
        'category',
        'description',
        'deadline',
        'published_date',
        'buyer',
        'value',
        'location',
        'documents',
        'project_id',
        'detail_url',
    ]
    
    # Add any extra columns
    all_keys = set()
    for tender in tenders:
        all_keys.update(tender.keys())
    
    for key in sorted(all_keys):
        if key not in columns:
            columns.append(key)
    
    # Create DataFrame
    df = pd.DataFrame(tenders)
    df = df.reindex(columns=[c for c in columns if c in df.columns])
    
    # Save to CSV
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    logger.info(f"Saved {len(tenders)} tenders to {filename}")
    
    return df


def main():
    """Main entry point."""
    print("=" * 60)
    print("GGGI TENDER SCRAPER")
    print("=" * 60)
    print(f"Source: {TENDERS_URL}")
    print("=" * 60)
    
    start_time = datetime.now()
    
    # Scrape all tenders
    tenders = scrape_all_tenders()
    
    # Generate filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"/workspace/gggi_tenders_{timestamp}.csv"
    latest_file = "/workspace/gggi_tenders_latest.csv"
    
    # Save to CSV
    if tenders:
        df = save_to_csv(tenders, output_file)
        save_to_csv(tenders, latest_file)
        
        print("\n" + "=" * 60)
        print("SCRAPING COMPLETE")
        print("=" * 60)
        print(f"Total tenders scraped: {len(tenders)}")
        print(f"Output file: {output_file}")
        print(f"Latest file: {latest_file}")
        
        # Description stats
        if df is not None and 'description' in df.columns:
            desc_filled = df['description'].apply(lambda x: len(str(x)) > 0 if x else False).sum()
            print(f"\nTenders with description: {desc_filled}/{len(tenders)}")
        
        print("=" * 60)
        
        # Show all tenders
        print("\nALL SCRAPED TENDERS:")
        print("-" * 60)
        for i, tender in enumerate(tenders):
            print(f"\n{i+1}. {tender.get('title', 'N/A')[:70]}")
            print(f"   Reference: {tender.get('reference', 'N/A')}")
            print(f"   Deadline: {tender.get('deadline', 'N/A')}")
            desc = tender.get('description', '')
            if desc:
                print(f"   Description: {desc[:150]}...")
            print(f"   URL: {tender.get('detail_url', 'N/A')}")
    else:
        print("\nNo tenders found.")
    
    end_time = datetime.now()
    print(f"\nExecution time: {end_time - start_time}")
    
    return tenders


if __name__ == "__main__":
    main()
