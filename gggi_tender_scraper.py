#!/usr/bin/env python3
"""
GGGI Tender Scraper
Scrapes tender information from https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
Uses Selenium to render JavaScript and extract tender data.
Visits each tender's detail page to extract full description.
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
        chrome_options.binary_location = "/usr/local/bin/google-chrome"
        driver = webdriver.Chrome(options=chrome_options)
    
    return driver


def clean_text(text):
    """Clean and normalize text."""
    if text is None:
        return ""
    text = re.sub(r'\s+', ' ', str(text).strip())
    return text


def wait_for_tenders(driver, timeout=30):
    """Wait for tenders to load on the page."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "containerProjects"))
        )
        # Wait longer for AJAX content to load
        time.sleep(5)
        
        # Try multiple times to find tenders
        for _ in range(3):
            elements = driver.find_elements(By.CSS_SELECTOR, "[data-timescalesid]")
            if elements:
                return True
            time.sleep(2)
        
        # Check if there's an empty message
        try:
            container_text = driver.find_element(By.ID, "containerProjects").text.lower()
            if "no " in container_text or "there are no" in container_text:
                return True  # Page loaded but no tenders
        except:
            pass
        
        return True  # Return true anyway, let extraction handle it
    except TimeoutException:
        logger.warning("Timeout waiting for tenders to load")
        return True  # Try to extract anyway


def extract_tenders_from_page(driver, mode):
    """Extract tender information from the current page."""
    tenders = []
    
    try:
        tender_elements = driver.find_elements(By.CSS_SELECTOR, "[data-timescalesid]")
        logger.info(f"Found {len(tender_elements)} tender elements on page")
        
        for elem in tender_elements:
            try:
                project_id = elem.get_attribute("data-timescalesid")
                
                # Extract title
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
                    if ":" in deadline_text:
                        deadline = deadline_text.split(":", 1)[1].strip()
                except NoSuchElementException:
                    pass
                
                tender_data = {
                    'mode': mode,
                    'project_id': project_id,
                    'title': title,
                    'deadline': deadline,
                    'detail_url': f"{PROJECT_DETAIL_URL}/{project_id}" if project_id else '',
                    'reference': '',
                    'status': '',
                    'category': '',
                    'description': '',  # Will be filled from detail page
                }
                
                # Extract table data from listing
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
                        except Exception:
                            continue
                except Exception:
                    pass
                
                tenders.append(tender_data)
                
            except Exception as e:
                logger.warning(f"Error extracting tender: {e}")
                continue
        
    except Exception as e:
        logger.error(f"Error finding tender elements: {e}")
    
    return tenders


def extract_description_from_detail_page(driver, tender_info):
    """
    Visit tender detail page and extract the full description.
    This is the main function to scrape description content from each tender's link.
    """
    details = tender_info.copy()
    
    try:
        detail_url = tender_info.get('detail_url')
        if not detail_url:
            return details
        
        logger.info(f"  -> Visiting detail page: {detail_url}")
        driver.get(detail_url)
        time.sleep(2)  # Wait for page to load
        
        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        # ============================================
        # EXTRACT DESCRIPTION FROM DETAIL PAGE
        # ============================================
        description = ""
        
        # Method 1: Look for "Further Information" or description in tables
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = clean_text(cells[0].get_text()).lower().strip(':').strip()
                    value = clean_text(cells[-1].get_text())
                    
                    # Look for description-related fields
                    if any(keyword in label for keyword in ['further information', 'description', 'summary', 'overview', 'details', 'brief']):
                        if len(value) > len(description):
                            description = value
                    
                    # Also extract other useful fields
                    if 'reference' in label and not details.get('reference'):
                        details['reference'] = value
                    elif 'status' in label and not details.get('status'):
                        details['status'] = value
                    elif 'category' in label or 'process' in label:
                        if not details.get('category'):
                            details['category'] = value
                    elif 'publish' in label or 'issue date' in label:
                        if not details.get('published_date'):
                            details['published_date'] = value
                    elif 'buyer' in label or 'authority' in label or 'organisation' in label:
                        if not details.get('buyer'):
                            details['buyer'] = value
                    elif 'value' in label or 'budget' in label:
                        if not details.get('value'):
                            details['value'] = value
                    elif 'location' in label or 'place' in label:
                        if not details.get('location'):
                            details['location'] = value
                    elif 'contact' in label and 'email' in label:
                        if not details.get('contact_email'):
                            details['contact_email'] = value
                    elif 'contact' in label and 'name' in label:
                        if not details.get('contact_name'):
                            details['contact_name'] = value
        
        # Method 2: Look for box-body content with description
        if not description or len(description) < 100:
            box_bodies = soup.find_all('div', class_=re.compile(r'box-body', re.IGNORECASE))
            for box in box_bodies:
                box_text = clean_text(box.get_text())
                # Skip navigation/menu content
                if len(box_text) > 200 and not any(skip in box_text.lower() for skip in ['login', 'register', 'menu', 'navigation', 'opt in', 'opt out']):
                    # Check if this looks like tender description content
                    if any(keyword in box_text.lower() for keyword in ['project', 'objective', 'scope', 'background', 'invit', 'proposal', 'tender', 'consulting']):
                        if len(box_text) > len(description):
                            description = box_text
        
        # Method 3: Look for main content area
        if not description or len(description) < 100:
            main_content = soup.find('div', id=re.compile(r'content|main', re.IGNORECASE))
            if main_content:
                content_text = clean_text(main_content.get_text())
                if len(content_text) > 200:
                    description = content_text
        
        # Method 4: Find all paragraphs that look like description
        if not description or len(description) < 100:
            paragraphs = soup.find_all('p')
            desc_parts = []
            for p in paragraphs:
                p_text = clean_text(p.get_text())
                if len(p_text) > 50 and any(keyword in p_text.lower() for keyword in ['project', 'objective', 'scope', 'gggi', 'invit', 'proposal']):
                    desc_parts.append(p_text)
            if desc_parts:
                description = ' '.join(desc_parts)
        
        # Clean up description - remove common boilerplate text
        if description:
            # Remove common footer/boilerplate sections
            boilerplate_markers = [
                'HOW TO OBTAIN THE DOCUMENTS',
                'ONLINE TENDER MANAGEMENT',
                'OPTING IN & OPTING OUT',
                'SUBMITTING YOUR RESPONSE',
                'NOTIFICATION EMAILS',
                'Please read Instructions on How to submit',
            ]
            
            for marker in boilerplate_markers:
                if marker in description:
                    description = description.split(marker)[0]
            
            description = clean_text(description)
        
        details['description'] = description
        logger.info(f"  -> Extracted description: {len(description)} characters")
        
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
                    tenders = extract_tenders_from_page(driver, mode)
                    logger.info(f"Extracted {len(tenders)} {mode} tenders")
                    all_tenders.extend(tenders)
                else:
                    logger.warning(f"Failed to load {mode} tenders page")
                    
            except Exception as e:
                logger.error(f"Error scraping {mode} tenders: {e}")
        
        logger.info(f"\nTotal tenders collected: {len(all_tenders)}")
        
        # ============================================
        # VISIT EACH TENDER'S DETAIL PAGE TO EXTRACT DESCRIPTION
        # ============================================
        if all_tenders:
            logger.info("\n" + "="*60)
            logger.info("FETCHING DESCRIPTIONS FROM EACH TENDER'S DETAIL PAGE")
            logger.info("="*60)
            
            for i, tender in enumerate(all_tenders):
                logger.info(f"\nProcessing {i + 1}/{len(all_tenders)}: {tender.get('title', tender.get('project_id', 'Unknown'))[:60]}")
                
                try:
                    # Visit detail page and extract description
                    updated_tender = extract_description_from_detail_page(driver, tender)
                    all_tenders[i] = updated_tender
                except Exception as e:
                    logger.warning(f"Error fetching detail for tender {i}: {e}")
                
                time.sleep(0.5)  # Be polite to the server
        
    finally:
        driver.quit()
    
    return all_tenders


def save_to_csv(tenders, filename):
    """Save tender data to CSV file."""
    if not tenders:
        logger.warning("No tender data to save")
        return None
    
    # Preferred column order - Description is prominently placed
    preferred_order = [
        'mode', 
        'reference', 
        'title', 
        'status', 
        'category', 
        'description',  # Full description from detail page
        'deadline', 
        'published_date',
        'buyer',
        'value',
        'location',
        'contact_name',
        'contact_email',
        'documents',
        'project_id', 
        'detail_url',
        'further_information',
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
        
        # Show description stats
        if df is not None and 'description' in df.columns:
            desc_lengths = df['description'].apply(lambda x: len(str(x)) if x else 0)
            print(f"\nDescription column stats:")
            print(f"  - Average length: {desc_lengths.mean():.0f} characters")
            print(f"  - Min length: {desc_lengths.min()} characters")
            print(f"  - Max length: {desc_lengths.max()} characters")
        
        print("=" * 60)
        
        # Show samples with description preview
        print("\nSample tender data with descriptions:")
        for tender in tenders[:3]:
            print(f"\n- Title: {tender.get('title', 'N/A')[:70]}")
            print(f"  Reference: {tender.get('reference', 'N/A')}")
            print(f"  Deadline: {tender.get('deadline', 'N/A')}")
            desc = tender.get('description', '')
            if desc:
                print(f"  Description: {desc[:200]}...")
            print(f"  URL: {tender.get('detail_url', 'N/A')}")
    else:
        print("\nNo tenders found.")
    
    end_time = datetime.now()
    logger.info(f"Total execution time: {end_time - start_time}")
    
    return tenders


if __name__ == "__main__":
    main()
