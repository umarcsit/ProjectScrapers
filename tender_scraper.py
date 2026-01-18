#!/usr/bin/env python3
"""
Comprehensive Tender Scraper for GGGI Tenders
Scrapes ALL tender information from https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
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
import csv
import time
import re
from datetime import datetime

TENDERS_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Current"
BASE_URL = "https://in-tendhost.co.uk/gggi/aspx"


def setup_driver():
    """Set up Chrome WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(90)
    return driver


def clean_text(text):
    """Clean text content."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.strip())


def clean_key(key):
    """Clean key for CSV column."""
    if not key:
        return ""
    key = re.sub(r'[^\w\s]', '', key).strip().replace(' ', '_')
    return re.sub(r'_+', '_', key)[:50]


def load_page_with_retry(driver, url, max_retries=3):
    """Load page with retries."""
    for attempt in range(max_retries):
        try:
            print(f"  Loading (attempt {attempt + 1})...")
            driver.get(url)
            
            # Wait for page to be ready
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Wait for specific GGGI content
            time.sleep(8)  # Generous wait for JS
            
            # Check if we got the right page
            if 'GGGI' in driver.page_source or 'containerProjects' in driver.page_source:
                print("  Page loaded successfully!")
                return True
            
            print(f"  Page content not as expected, retrying...")
            time.sleep(2)
            
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            time.sleep(3)
    
    return False


def scrape_listing_page(driver):
    """Scrape the tender listing page."""
    print("\n" + "="*60)
    print("Loading GGGI Tender Listing Page")
    print("="*60)
    
    if not load_page_with_retry(driver, TENDERS_URL):
        print("Failed to load page after retries")
        return []
    
    # Additional wait for dynamic content
    time.sleep(5)
    
    page_source = driver.page_source
    
    # Save for debugging
    with open('raw_listing_page.html', 'w', encoding='utf-8') as f:
        f.write(page_source)
    
    # Check page title
    soup = BeautifulSoup(page_source, 'html.parser')
    title = soup.find('title')
    print(f"Page title: {title.get_text() if title else 'No title'}")
    
    tenders = []
    
    # Find tender rows by data-timescalesid
    tender_rows = soup.find_all('div', attrs={'data-timescalesid': True})
    print(f"Found {len(tender_rows)} tender rows")
    
    for row in tender_rows:
        tender = extract_tender_from_row(row)
        if tender.get('Title'):
            tenders.append(tender)
    
    # Alternative: Find by box class if no rows found
    if not tenders:
        print("Trying alternative extraction method...")
        container = soup.find('div', id='containerProjects')
        if container:
            boxes = container.find_all('div', class_='box')
            print(f"Found {len(boxes)} boxes in container")
            for box in boxes:
                tender = extract_tender_from_box(box)
                if tender.get('Title'):
                    tenders.append(tender)
    
    print(f"\nExtracted {len(tenders)} tenders")
    return tenders


def extract_tender_from_row(row):
    """Extract tender data from a row element."""
    tender = {}
    
    # Project ID
    project_id = row.get('data-timescalesid')
    if project_id:
        tender['Project_ID'] = project_id
        tender['Detail_URL'] = f"{BASE_URL}/ProjectManage/{project_id}"
    
    # Find box inside row
    box = row.find('div', class_='box')
    if box:
        tender.update(extract_tender_from_box(box))
    
    return tender


def extract_tender_from_box(box):
    """Extract tender data from a box element."""
    tender = {}
    
    # Header section
    header = box.find('div', class_='box-header')
    if header:
        # Title from first col or font-14 element
        title_elem = header.find('div', class_=lambda x: x and ('font-14' in str(x) or 'bold' in str(x)))
        if title_elem:
            tender['Title'] = clean_text(title_elem.get_text())
        
        if not tender.get('Title'):
            cols = header.find_all('div', recursive=False)
            for col in cols:
                text = clean_text(col.get_text())
                if text and 'Deadline' not in text and len(text) > 10:
                    tender['Title'] = text
                    break
        
        # Deadline from text-right div
        deadline_div = header.find('div', class_=lambda x: x and 'text-right' in str(x))
        if deadline_div:
            deadline_text = clean_text(deadline_div.get_text())
            tender['Deadline_Full'] = deadline_text
            
            # Extract date
            date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4}\s*\d{1,2}:\d{2})', deadline_text)
            if date_match:
                tender['Deadline_Date'] = date_match.group(1)
            
            # Extract timezone
            tz_match = re.search(r'\(UTC\s*[+-]?\d{2}:\d{2}\)[^)]*', deadline_text)
            if tz_match:
                tender['Timezone'] = tz_match.group(0)
    
    # Body section - extract all table data
    body = box.find('div', class_='box-body')
    if body:
        for table in body.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label_cell = cells[0]
                    label = label_cell.find('label')
                    key = clean_text(label.get_text() if label else label_cell.get_text())
                    
                    # Get value from last cell
                    value = clean_text(cells[-1].get_text())
                    
                    if key and value and key != value:
                        key_clean = clean_key(key)
                        if key_clean and key_clean not in tender:
                            tender[key_clean] = value
    
    return tender


def scrape_detail_page(driver, tender, index, total):
    """Scrape detail page for ALL available information."""
    project_id = tender.get('Project_ID')
    if not project_id:
        tender['Detail_Status'] = 'No Project ID'
        return
    
    print(f"\n[{index}/{total}] Scraping detail for Project {project_id}")
    print(f"  Title: {tender.get('Title', 'N/A')[:50]}...")
    
    detail_url = f"{BASE_URL}/ProjectManage/{project_id}"
    
    try:
        driver.get(detail_url)
        time.sleep(8)
        
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        page_source = driver.page_source
        
        if index == 1:
            with open('raw_detail_page.html', 'w', encoding='utf-8') as f:
                f.write(page_source)
        
        soup = BeautifulSoup(page_source, 'html.parser')
        tender['Detail_Status'] = 'Scraped'
        
        description_parts = []
        
        # Extract ALL label:value pairs from the page
        for label in soup.find_all('label'):
            label_text = clean_text(label.get_text())
            # Remove trailing colon and spaces
            label_text = re.sub(r'[\s:]+$', '', label_text).strip()
            
            if not label_text or len(label_text) < 2:
                continue
            
            # Get value from next sibling or parent's next sibling
            parent = label.parent
            if parent:
                # Try to find value in same row
                row = parent.find_parent('tr')
                if row:
                    cells = row.find_all('td')
                    for cell in cells:
                        if cell != label.parent:
                            value = clean_text(cell.get_text())
                            if value and value != label_text:
                                key_clean = clean_key(label_text)
                                if key_clean and key_clean not in tender and len(value) < 2000:
                                    tender[key_clean] = value
                                
                                # Check for description content
                                if any(kw in label_text.lower() for kw in ['description', 'scope', 'background', 'objective', 'summary', 'overview', 'requirement']):
                                    description_parts.append(f"{label_text}: {value}")
                                break
        
        # Extract all table data systematically
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # First cell with label
                    label_cell = cells[0]
                    label = label_cell.find('label')
                    key = clean_text(label.get_text() if label else label_cell.get_text())
                    key = re.sub(r'[\s:]+$', '', key).strip()
                    
                    # Get value from other cells
                    for cell in cells[1:]:
                        value = clean_text(cell.get_text())
                        if value and value != key and len(value) > 1:
                            key_clean = clean_key(key)
                            if key_clean and key_clean not in tender:
                                tender[key_clean] = value[:2000]
                            
                            if any(kw in key.lower() for kw in ['description', 'scope', 'background', 'objective']):
                                description_parts.append(f"{key}: {value}")
                            break
        
        # Look for document/attachment links
        docs = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = clean_text(link.get_text())
            if any(ext in href for ext in ['.pdf', '.doc', '.xls', '.zip', 'download', 'filedownload']):
                if text and len(text) > 2:
                    docs.append(text)
        if docs:
            tender['Available_Documents'] = ' | '.join(list(set(docs))[:10])
        
        # Look for longer text blocks for description
        for elem in soup.find_all(['div', 'p', 'td', 'span']):
            text = clean_text(elem.get_text())
            if 300 < len(text) < 8000:
                text_lower = text.lower()
                if any(kw in text_lower[:300] for kw in ['background', 'objective', 'scope', 'gggi', 'project', 'assignment', 'consulting', 'proposal']):
                    description_parts.append(text)
        
        # Combine descriptions
        if description_parts:
            seen = set()
            unique = []
            for part in description_parts:
                norm = part[:100].lower()
                if norm not in seen:
                    seen.add(norm)
                    unique.append(part)
            unique.sort(key=len, reverse=True)
            tender['Description'] = ' ||| '.join(unique[:3])[:10000]
        
        field_count = len([k for k in tender.keys() if tender[k]])
        print(f"  Extracted {field_count} fields, Description: {len(tender.get('Description', ''))} chars")
        
    except Exception as e:
        print(f"  Error: {e}")
        tender['Detail_Status'] = f'Error: {str(e)[:50]}'


def save_to_csv(tenders, filename='gggi_tenders.csv'):
    """Save all tenders to comprehensive CSV."""
    if not tenders:
        print("No tenders to save")
        return
    
    # Get all keys
    all_keys = set()
    for t in tenders:
        all_keys.update(t.keys())
    
    # Comprehensive priority order
    priority = [
        # Core identification
        'Title', 'Project_ID', 'Reference', 'Status', 'Category', 'Process', 'Type',
        'Procurement_Method', 'Quality_Cumulative_Split',
        
        # Dates
        'Published_Date', 'Issue_Date', 'OpenDate', 'Contract_Start',
        'Deadline_Date', 'Deadline_Full', 'Deadline_For_Applications',
        'CloseDate', 'Contract_End', 'EstAwardDate', 'Award', 'DateExtensionClause',
        'Timezone',
        
        # Financial
        'Value', 'Budget', 'EstValue', 'Estimated_Value', 'Currency',
        
        # Location
        'Location', 'Country', 'Region', 'Place_of_Performance',
        
        # Organization
        'Organization', 'Department', 'GGGI_Office', 'Contracting_Authority',
        'Contact', 'Contact_Person', 'Email', 'Phone',
        
        # Bid Information  
        'Number_of_bids_received', 'Number_of_rejected_bids',
        'No_of_Bids_passed_Technical_Evalution', 
        'No_of_Bids_that_did_not_pass_Technical_Evaluation',
        'Name_and_Address_of_successful_biddersupplier',
        'Evaluated_bid_price_of_successful_bid',
        'Bid_Evaluation_Summary',
        
        # Content
        'Description', 'Summary', 'Scope', 'Background', 'Objective', 'Overview',
        'Requirements', 'Eligibility', 'Qualification_Criteria',
        
        # Documents
        'Available_Documents', 'Attachment', 'Documents',
        
        # Technical
        'Detail_URL', 'Detail_Status'
    ]
    
    columns = []
    for col in priority:
        if col in all_keys:
            columns.append(col)
            all_keys.discard(col)
    columns.extend(sorted(all_keys))
    
    # Write CSV
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(tenders)
    
    print(f"\n{'='*60}")
    print(f"SAVED: {filename}")
    print(f"{'='*60}")
    print(f"Tenders: {len(tenders)}")
    print(f"Columns: {len(columns)}")
    print("\nColumn list:")
    for i, col in enumerate(columns, 1):
        count = sum(1 for t in tenders if t.get(col))
        print(f"  {i:2}. {col} ({count}/{len(tenders)})")


def main():
    print("="*60)
    print("GGGI COMPREHENSIVE TENDER SCRAPER")
    print(f"Started: {datetime.now()}")
    print("="*60)
    
    driver = None
    tenders = []
    
    try:
        print("\nInitializing WebDriver...")
        driver = setup_driver()
        print("WebDriver ready!")
        
        # Step 1: Scrape listing
        tenders = scrape_listing_page(driver)
        
        if tenders:
            print(f"\nFound {len(tenders)} tenders:")
            for i, t in enumerate(tenders, 1):
                print(f"  {i}. [{t.get('Project_ID', '?')}] {t.get('Title', 'N/A')[:50]}...")
            
            # Step 2: Scrape details
            print("\n" + "="*60)
            print("Scraping Detail Pages")
            print("="*60)
            
            for i, tender in enumerate(tenders, 1):
                scrape_detail_page(driver, tender, i, len(tenders))
                time.sleep(3)
        
        # Step 3: Save
        print("\n" + "="*60)
        print("Saving Results")
        print("="*60)
        save_to_csv(tenders)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        if tenders:
            save_to_csv(tenders)
    
    finally:
        if driver:
            driver.quit()
    
    print(f"\nFinished: {datetime.now()}")


if __name__ == "__main__":
    main()
