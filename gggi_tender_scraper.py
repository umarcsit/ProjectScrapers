#!/usr/bin/env python3
"""
GGGI Tender Scraper
Scrapes tender information from https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
Uses Selenium to render JavaScript and extract tender data.
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
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# URLs
BASE_URL = "https://in-tendhost.co.uk"
TENDERS_CURRENT_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Current"
TENDERS_FORTHCOMING_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Forthcoming"
TENDERS_AWARDED_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Awarded"
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
        # Fallback to system Chrome
        chrome_options.binary_location = "/usr/local/bin/google-chrome"
        driver = webdriver.Chrome(options=chrome_options)
    
    return driver


def clean_text(text):
    """Clean and normalize text."""
    if text is None:
        return ""
    text = re.sub(r'\s+', ' ', str(text).strip())
    return text


def wait_for_tenders(driver, timeout=20):
    """Wait for tenders to load on the page."""
    try:
        # Wait for the container to be present
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "containerProjects"))
        )
        
        # Wait a bit for AJAX to complete
        time.sleep(3)
        
        # Check if tenders are loaded or empty message appears
        try:
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "[data-timescalesid]")) > 0 or
                          "no " in d.find_element(By.ID, "containerProjects").text.lower()
            )
        except TimeoutException:
            pass
        
        return True
    except TimeoutException:
        logger.warning("Timeout waiting for tenders to load")
        return False


def extract_tenders_from_page(driver, mode):
    """Extract tender information from the current page."""
    tenders = []
    
    try:
        # Find all tender containers
        tender_elements = driver.find_elements(By.CSS_SELECTOR, "[data-timescalesid]")
        logger.info(f"Found {len(tender_elements)} tender elements on page")
        
        for elem in tender_elements:
            try:
                project_id = elem.get_attribute("data-timescalesid")
                
                # Extract title from box-header
                title = ""
                try:
                    header = elem.find_element(By.CSS_SELECTOR, ".box-header .font-14")
                    title = clean_text(header.text)
                except NoSuchElementException:
                    try:
                        header = elem.find_element(By.CSS_SELECTOR, ".box-header")
                        title = clean_text(header.text.split('\n')[0])
                    except NoSuchElementException:
                        pass
                
                # Extract deadline
                deadline = ""
                try:
                    deadline_elem = elem.find_element(By.CSS_SELECTOR, ".box-header .text-right")
                    deadline_text = clean_text(deadline_elem.text)
                    # Extract date from text like "Deadline For Applications : 15 Jan 2026 12:00:00"
                    if ":" in deadline_text:
                        deadline = deadline_text.split(":", 1)[1].strip()
                except NoSuchElementException:
                    pass
                
                # Extract table data
                tender_data = {
                    'mode': mode,
                    'project_id': project_id,
                    'title': title,
                    'deadline': deadline,
                    'detail_url': f"{PROJECT_DETAIL_URL}/{project_id}" if project_id else '',
                }
                
                # Try to extract table rows
                try:
                    rows = elem.find_elements(By.CSS_SELECTOR, "table tr")
                    for row in rows:
                        try:
                            cells = row.find_elements(By.CSS_SELECTOR, "th, td")
                            if len(cells) >= 2:
                                label = clean_text(cells[0].text).lower().strip(':')
                                value = clean_text(cells[-1].text)
                                
                                if 'status' in label:
                                    tender_data['status'] = value
                                elif 'reference' in label:
                                    tender_data['reference'] = value
                                elif 'process' in label or 'category' in label:
                                    tender_data['category'] = value
                                elif 'further information' in label:
                                    tender_data['further_information'] = value
                                elif 'title' in label and not tender_data.get('title'):
                                    tender_data['title'] = value
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"Error extracting table data: {e}")
                
                tenders.append(tender_data)
                
            except Exception as e:
                logger.warning(f"Error extracting tender: {e}")
                continue
        
    except Exception as e:
        logger.error(f"Error finding tender elements: {e}")
    
    return tenders


def extract_detail_page(driver, tender_info):
    """Extract detailed information from a tender's detail page."""
    details = tender_info.copy()
    
    try:
        detail_url = tender_info.get('detail_url')
        if not detail_url:
            return details
        
        driver.get(detail_url)
        time.sleep(2)  # Wait for page to load
        
        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        # Field mappings
        field_mappings = {
            'reference': ['reference', 'ref', 'tender ref', 'project ref'],
            'title': ['title', 'name', 'tender title', 'project name'],
            'description': ['description', 'summary', 'overview', 'further information', 'brief description'],
            'buyer': ['buyer', 'authority', 'organisation', 'organization', 'contracting authority', 'customer'],
            'value': ['value', 'budget', 'estimated value', 'contract value', 'amount'],
            'published_date': ['published', 'publication date', 'issue date', 'date published'],
            'deadline': ['deadline', 'closing', 'submission deadline', 'closing date', 'deadline for applications'],
            'category': ['category', 'type', 'classification', 'cpv', 'process'],
            'location': ['location', 'place', 'region', 'country', 'delivery location'],
            'contact_name': ['contact name', 'contact person'],
            'contact_email': ['contact email', 'email', 'e-mail'],
            'status': ['status', 'state', 'tender status'],
            'procedure': ['procedure', 'procurement type', 'tender type'],
        }
        
        # Extract from tables
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = clean_text(cells[0].get_text()).lower().strip(':').strip()
                    value = clean_text(cells[-1].get_text())
                    
                    for field_name, patterns in field_mappings.items():
                        if any(p in label for p in patterns):
                            if field_name not in details or not details.get(field_name):
                                details[field_name] = value
                            break
        
        # Extract documents
        doc_links = soup.find_all('a', href=re.compile(r'\.(pdf|doc|docx|xls|xlsx)', re.IGNORECASE))
        if doc_links:
            doc_names = [clean_text(link.get_text()) for link in doc_links if clean_text(link.get_text())]
            if doc_names:
                details['documents'] = '; '.join(doc_names[:10])
        
    except Exception as e:
        logger.warning(f"Error extracting detail page: {e}")
    
    return details


def scrape_tenders():
    """Main function to scrape all tenders."""
    logger.info("Starting GGGI Tender Scraper with Selenium")
    
    driver = setup_driver()
    all_tenders = []
    
    try:
        # URLs and their modes
        pages = [
            (TENDERS_CURRENT_URL, "Current"),
            (TENDERS_FORTHCOMING_URL, "Forthcoming"),
            (TENDERS_AWARDED_URL, "Awarded"),
        ]
        
        for url, mode in pages:
            logger.info(f"\n{'='*50}\nFetching {mode} tenders from {url}\n{'='*50}")
            
            try:
                driver.get(url)
                
                if wait_for_tenders(driver):
                    # Save HTML for debugging
                    if mode == "Current":
                        with open('/workspace/listing_page.html', 'w', encoding='utf-8') as f:
                            f.write(driver.page_source)
                    
                    tenders = extract_tenders_from_page(driver, mode)
                    logger.info(f"Extracted {len(tenders)} {mode} tenders")
                    all_tenders.extend(tenders)
                else:
                    logger.warning(f"Failed to load {mode} tenders page")
                    
            except Exception as e:
                logger.error(f"Error scraping {mode} tenders: {e}")
        
        logger.info(f"\nTotal tenders collected: {len(all_tenders)}")
        
        # Fetch detail pages
        if all_tenders:
            logger.info("\nFetching detail pages for additional information...")
            for i, tender in enumerate(all_tenders):
                logger.info(f"Processing {i + 1}/{len(all_tenders)}: {tender.get('title', tender.get('project_id', 'Unknown'))[:50]}")
                
                try:
                    updated_tender = extract_detail_page(driver, tender)
                    all_tenders[i] = updated_tender
                    
                    # Save first detail page for debugging
                    if i == 0:
                        with open('/workspace/detail_page_sample.html', 'w', encoding='utf-8') as f:
                            f.write(driver.page_source)
                except Exception as e:
                    logger.warning(f"Error fetching detail for tender {i}: {e}")
                
                time.sleep(0.5)
        
    finally:
        driver.quit()
    
    return all_tenders


def save_to_csv(tenders, filename):
    """Save tender data to CSV file."""
    if not tenders:
        logger.warning("No tender data to save")
        return None
    
    # Preferred column order
    preferred_order = [
        'mode', 'reference', 'title', 'status', 'category', 'description',
        'further_information', 'deadline', 'buyer', 'value', 'published_date',
        'location', 'contact_name', 'contact_email', 'procedure', 'documents',
        'project_id', 'detail_url'
    ]
    
    # Collect all keys
    all_keys = set()
    for tender in tenders:
        all_keys.update(tender.keys())
    
    # Sort columns
    columns = []
    for col in preferred_order:
        if col in all_keys:
            columns.append(col)
            all_keys.discard(col)
    columns.extend(sorted(all_keys))
    
    # Create DataFrame
    df = pd.DataFrame(tenders)
    df = df.reindex(columns=[c for c in columns if c in df.columns])
    
    # Save to CSV
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    logger.info(f"Saved {len(tenders)} tenders to {filename}")
    
    return df


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("GGGI Tender Scraper Started")
    logger.info("=" * 60)
    
    start_time = datetime.now()
    
    # Scrape tenders
    tenders = scrape_tenders()
    
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
        print(f"Total tenders found: {len(tenders)}")
        print(f"Output file: {output_file}")
        print(f"Latest file: {latest_file}")
        
        if df is not None and 'mode' in df.columns:
            print("\nTenders by type:")
            for mode in df['mode'].unique():
                count = len(df[df['mode'] == mode])
                print(f"  - {mode}: {count}")
        
        print("=" * 60)
        
        # Show samples
        print("\nSample tender data:")
        for tender in tenders[:3]:
            print(f"\n- Title: {tender.get('title', 'N/A')[:80]}")
            print(f"  Reference: {tender.get('reference', 'N/A')}")
            print(f"  Status: {tender.get('status', 'N/A')}")
            print(f"  Deadline: {tender.get('deadline', 'N/A')}")
            print(f"  URL: {tender.get('detail_url', 'N/A')}")
    else:
        print("\nNo tenders found.")
    
    end_time = datetime.now()
    logger.info(f"Total execution time: {end_time - start_time}")
    
    return tenders


if __name__ == "__main__":
    main()
