#!/usr/bin/env python3
"""
Tender Scraper for GGGI Tenders
Scrapes tender information from https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
Extracts main listing data and visits each tender's detail page for descriptions.
Uses Selenium for JavaScript rendering.
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
from urllib.parse import urljoin
from datetime import datetime

# Target URL
TENDERS_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Current"
BASE_URL = "https://in-tendhost.co.uk/gggi/aspx"


def setup_driver():
    """Set up Chrome WebDriver with headless options."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver


def clean_text(text):
    """Clean and normalize text content."""
    if text is None:
        return ""
    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def wait_for_page_load(driver, timeout=30):
    """Wait for the page to load completely."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(5)  # Additional wait for dynamic content
        return True
    except TimeoutException:
        print("Timeout waiting for page to load")
        return False


def scrape_tender_listing(driver):
    """Scrape the main tender listing page."""
    print(f"Loading tender listing page: {TENDERS_URL}")
    driver.get(TENDERS_URL)
    
    if not wait_for_page_load(driver, timeout=30):
        print("Page load timeout")
        return []
    
    # Wait for the tenders container to load
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "containerProjects"))
        )
    except TimeoutException:
        print("Tenders container not found")
    
    time.sleep(3)  # Extra wait for content
    
    page_source = driver.page_source
    with open('raw_listing_page.html', 'w', encoding='utf-8') as f:
        f.write(page_source)
    print("Saved rendered HTML to raw_listing_page.html")
    
    soup = BeautifulSoup(page_source, 'html.parser')
    tenders = []
    
    # Find all tender rows by data-timescalesid attribute (this is the ProjectID)
    tender_rows = soup.find_all('div', class_='row', attrs={'data-timescalesid': True})
    print(f"Found {len(tender_rows)} tender rows with data-timescalesid")
    
    for row in tender_rows:
        tender_data = {}
        
        # Get the ProjectID from the data attribute
        project_id = row.get('data-timescalesid')
        if project_id:
            tender_data['Project_ID'] = project_id
            # Construct the detail URL using the found pattern
            tender_data['Detail_URL'] = f"{BASE_URL}/ProjectManage/{project_id}"
        
        # Find the box inside this row
        box = row.find('div', class_='box')
        if not box:
            continue
        
        # Extract title from box-header
        header = box.find('div', class_='box-header')
        if header:
            # Title is typically in a bold font-14 div
            title_elem = header.find('div', class_=lambda x: x and 'font-14' in x)
            if title_elem:
                tender_data['Title'] = clean_text(title_elem.get_text())
            elif header.find('div', class_='col-md-6'):
                # Try first col-md-6 that's not text-right
                cols = header.find_all('div', class_=lambda x: x and 'col-md-6' in x)
                for col in cols:
                    if col.get('class') and 'text-right' not in ' '.join(col.get('class', [])):
                        tender_data['Title'] = clean_text(col.get_text())
                        break
            
            # Deadline is in the text-right div
            deadline_div = header.find('div', class_=lambda x: x and 'text-right' in str(x))
            if deadline_div:
                deadline_text = clean_text(deadline_div.get_text())
                # Parse out just the date/time part
                if 'Deadline' in deadline_text:
                    # Extract everything after the colon
                    deadline_match = re.search(r':\s*(.+)', deadline_text)
                    if deadline_match:
                        tender_data['Deadline'] = deadline_match.group(1).strip()
                else:
                    tender_data['Deadline'] = deadline_text
        
        # Extract table data from box-body
        body = box.find('div', class_='box-body')
        if body:
            table = body.find('table')
            if table:
                for row_tr in table.find_all('tr'):
                    cells = row_tr.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # First cell is usually the label (th or first td)
                        label_cell = cells[0]
                        label = label_cell.find('label')
                        if label:
                            key = clean_text(label.get_text())
                        else:
                            key = clean_text(label_cell.get_text())
                        
                        # Value is in the last td
                        value = clean_text(cells[-1].get_text())
                        
                        # Clean up key name for CSV column
                        if key and value:
                            key_clean = re.sub(r'[^\w\s]', '', key).strip().replace(' ', '_')
                            if key_clean and key_clean not in ['', 'label'] and len(key_clean) < 50:
                                tender_data[key_clean] = value
        
        # Only add if we have a title
        if tender_data.get('Title') and len(tender_data.get('Title', '')) > 5:
            tenders.append(tender_data)
    
    print(f"Total tenders extracted: {len(tenders)}")
    return tenders


def scrape_detail_page(driver, url, index, total):
    """Scrape a tender detail page for additional information including description."""
    detail_data = {
        'Description': '',
        'Detail_Page_Scraped': 'No'
    }
    
    if not url:
        detail_data['Detail_Page_Scraped'] = 'No URL'
        return detail_data
    
    try:
        print(f"  [{index}/{total}] Loading: {url}")
        driver.get(url)
        wait_for_page_load(driver, timeout=30)
        time.sleep(3)
        
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        detail_data['Detail_Page_Scraped'] = 'Yes'
        
        # Save first detail page for debugging
        if index == 1:
            with open('raw_detail_page.html', 'w', encoding='utf-8') as f:
                f.write(page_source)
            print("    Saved first detail page to raw_detail_page.html")
        
        description_parts = []
        
        # Find all tables on the detail page and extract data
        tables = soup.find_all('table')
        for table in tables:
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # Get label from first cell
                    label_cell = cells[0]
                    label_elem = label_cell.find('label')
                    if label_elem:
                        key = clean_text(label_elem.get_text())
                    else:
                        key = clean_text(label_cell.get_text())
                    
                    # Get value from last cell
                    value = clean_text(cells[-1].get_text())
                    
                    if key and value and key.lower() != value.lower():
                        # Store the data with cleaned key
                        key_clean = re.sub(r'[^\w\s]', '', key).strip().replace(' ', '_')
                        if key_clean and key_clean not in detail_data and len(key_clean) < 50:
                            detail_data[key_clean] = value
                        
                        # Check if this is description-related
                        key_lower = key.lower()
                        if any(kw in key_lower for kw in ['description', 'summary', 'scope', 'detail', 'overview', 'background', 'objective', 'requirement']):
                            if len(value) > 30:
                                description_parts.append(f"{key}: {value}")
        
        # Look for description in box-body divs or content areas
        content_areas = soup.find_all('div', class_=lambda x: x and any(c in str(x) for c in ['box-body', 'content', 'description']))
        for area in content_areas:
            # Look for paragraphs with substantial text
            for p in area.find_all('p'):
                text = clean_text(p.get_text())
                if len(text) > 100 and text not in str(description_parts):
                    description_parts.append(text)
        
        # Look for labeled sections with descriptions
        for label in soup.find_all(['label', 'strong', 'b', 'th', 'h3', 'h4', 'h5']):
            label_text = clean_text(label.get_text()).lower()
            if any(kw in label_text for kw in ['description', 'summary', 'scope', 'requirement', 'overview', 'background', 'objective']):
                # Get the next sibling or parent's text content
                parent = label.parent
                if parent:
                    # Get text after the label
                    parent_text = clean_text(parent.get_text())
                    label_clean = clean_text(label.get_text())
                    # Remove the label text from parent text
                    remaining_text = parent_text.replace(label_clean, '').strip()
                    if len(remaining_text) > 30:
                        description_parts.append(f"{label_text.title()}: {remaining_text}")
        
        # Look for any textarea or input fields that might contain descriptions
        for textarea in soup.find_all('textarea'):
            text = clean_text(textarea.get_text())
            if text and len(text) > 50:
                description_parts.append(text)
        
        # Combine description parts
        if description_parts:
            # Remove duplicates while preserving order
            seen = set()
            unique_parts = []
            for part in description_parts:
                # Normalize for comparison (first 100 chars)
                normalized = part[:100].lower().strip()
                if normalized not in seen and len(part) > 30:
                    seen.add(normalized)
                    unique_parts.append(part)
            
            # Sort by length (prefer longer descriptions)
            unique_parts.sort(key=len, reverse=True)
            detail_data['Description'] = ' | '.join(unique_parts[:3])[:4000]
        
        print(f"    Extracted {len(detail_data)} fields, Description length: {len(detail_data.get('Description', ''))}")
        
    except Exception as e:
        print(f"    Error: {e}")
        detail_data['Detail_Page_Scraped'] = 'Error'
        detail_data['Error'] = str(e)
    
    return detail_data


def save_to_csv(tenders, filename='gggi_tenders.csv'):
    """Save tenders to a CSV file with all extracted columns."""
    if not tenders:
        print("No tenders to save")
        return False
    
    # Collect all unique keys from all tenders
    all_keys = set()
    for tender in tenders:
        all_keys.update(tender.keys())
    
    # Preferred column order for readability
    preferred_order = [
        'Title', 'Project_ID', 'Reference', 'Tender_Reference', 'Ref', 'ID',
        'Status', 'Type', 'Category', 'Process', 'Procurement_Type', 'Procedure',
        'Published', 'Published_Date', 'Publication_Date', 'Open_Date', 'Start_Date',
        'Deadline', 'Closing_Date', 'Close_Date', 'Submission_Deadline', 'End_Date',
        'Value', 'Budget', 'Contract_Value', 'Estimated_Value', 'Amount',
        'Location', 'Region', 'Country', 'Place',
        'Organization', 'Buyer', 'Authority', 'Client', 'Department', 'Agency', 'Contact_Person',
        'Contact', 'Email', 'Phone', 'Telephone',
        'Description', 'Summary', 'Scope', 'Requirements', 'Objective', 'Background', 'Overview',
        'Further_Information', 'FurtherInformation', 'Additional_Information',
        'Detail_URL', 'Link', 'Detail_Page_Scraped', 'Error'
    ]
    
    # Build ordered column list
    columns = []
    for col in preferred_order:
        if col in all_keys:
            columns.append(col)
            all_keys.discard(col)
    # Add remaining columns alphabetically
    columns.extend(sorted(all_keys))
    
    # Write CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for tender in tenders:
            writer.writerow(tender)
    
    print(f"\n{'='*60}")
    print(f"RESULTS SAVED TO: {filename}")
    print(f"{'='*60}")
    print(f"Total tenders: {len(tenders)}")
    print(f"Total columns: {len(columns)}")
    print(f"\nColumns:")
    for i, col in enumerate(columns, 1):
        # Show sample value for this column
        sample = next((t.get(col, '')[:40] for t in tenders if t.get(col)), 'N/A')
        print(f"  {i:2}. {col}: {sample}...")
    print(f"{'='*60}")
    return True


def main():
    """Main entry point."""
    print("=" * 70)
    print("GGGI Tender Scraper")
    print(f"Target: {TENDERS_URL}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    driver = None
    tenders = []
    
    try:
        # Setup WebDriver
        print("\nSetting up Chrome WebDriver...")
        driver = setup_driver()
        print("WebDriver ready!\n")
        
        # Scrape tender listing
        print("-" * 70)
        print("STEP 1: Scraping tender listing page")
        print("-" * 70)
        tenders = scrape_tender_listing(driver)
        
        if tenders:
            # Print summary of found tenders
            print(f"\nFound {len(tenders)} tenders:")
            for i, t in enumerate(tenders, 1):
                title = t.get('Title', 'No Title')[:55]
                project_id = t.get('Project_ID', 'N/A')
                deadline = t.get('Deadline', 'No Deadline')[:30]
                print(f"  {i:2}. [{project_id}] {title}...")
                print(f"      Deadline: {deadline}")
            
            # Scrape detail pages
            print("\n" + "-" * 70)
            print("STEP 2: Scraping tender detail pages for descriptions")
            print("-" * 70)
            
            for i, tender in enumerate(tenders, 1):
                detail_url = tender.get('Detail_URL')
                if detail_url:
                    detail_data = scrape_detail_page(driver, detail_url, i, len(tenders))
                    # Merge detail data with tender data (don't overwrite existing fields)
                    for key, value in detail_data.items():
                        if key not in tender or not tender[key]:
                            tender[key] = value
                    time.sleep(2)  # Be polite to the server
                else:
                    tender['Description'] = ''
                    tender['Detail_Page_Scraped'] = 'No URL'
        else:
            print("\nNo tenders found on the listing page.")
            print("The website structure may have changed or there are no active tenders.")
        
        # Save results
        print("\n" + "-" * 70)
        print("STEP 3: Saving results to CSV")
        print("-" * 70)
        
        if tenders:
            save_to_csv(tenders)
        else:
            print("No tenders to save.")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        
        # Save whatever we have
        if tenders:
            print("\nSaving partial results...")
            save_to_csv(tenders)
    
    finally:
        if driver:
            driver.quit()
            print("\nWebDriver closed.")
    
    print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
