#!/usr/bin/env python3
"""
Tender Scraper for GGGI In-Tend Host
Scrapes current tenders from https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
Uses Selenium for JavaScript-rendered content
"""

import csv
import time
import re
import json
from datetime import datetime
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

# Base URL for the tender system
BASE_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Current"
SITE_BASE = "https://in-tendhost.co.uk/gggi/aspx"


def setup_driver():
    """Setup headless Chrome browser"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def wait_for_tenders(driver, timeout=30):
    """Wait for tender content to load"""
    try:
        # Wait for the containerProjects div which holds tenders
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "containerProjects"))
        )
        time.sleep(2)
        return True
    except TimeoutException:
        # Try waiting for any tender-related content
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-timescalesid]"))
            )
            return True
        except:
            pass
    return False


def extract_tenders_from_listing(driver):
    """Extract tender listings from the current page"""
    tenders = []
    
    # Save current page source for debugging
    with open('/workspace/current_page.html', 'w', encoding='utf-8') as f:
        f.write(driver.page_source)
    
    # Find all tender cards - they are div.row elements with data-timescalesid attribute
    try:
        tender_cards = driver.find_elements(By.CSS_SELECTOR, "div.row[data-timescalesid]")
        print(f"Found {len(tender_cards)} tender cards on this page")
        
        for card in tender_cards:
            try:
                tender = {}
                
                # Get project ID from data attribute
                project_id = card.get_attribute("data-timescalesid")
                tender['project_id'] = project_id
                
                # Extract title from box-header
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, ".box-header .col-md-6.bold.font-14")
                    tender['title'] = title_elem.text.strip()
                except NoSuchElementException:
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, ".box-header .bold")
                        tender['title'] = title_elem.text.strip()
                    except:
                        tender['title'] = ""
                
                # Extract deadline
                try:
                    deadline_elem = card.find_element(By.CSS_SELECTOR, ".box-header .col-md-6.text-right")
                    deadline_text = deadline_elem.text.strip()
                    deadline_text = deadline_text.replace("Deadline For Applications :", "").strip()
                    tender['deadline'] = deadline_text
                except NoSuchElementException:
                    tender['deadline'] = ""
                
                # Extract table data (Reference, Process, etc.)
                try:
                    table_rows = card.find_elements(By.CSS_SELECTOR, ".box-body table tr")
                    for row in table_rows:
                        try:
                            label_elem = row.find_element(By.TAG_NAME, "label")
                            label = label_elem.text.strip().lower().replace(" ", "_")
                            
                            value_elem = row.find_element(By.CSS_SELECTOR, "td.tender_details_width, td:last-child")
                            value = value_elem.text.strip()
                            
                            if label and value:
                                tender[label] = value
                        except NoSuchElementException:
                            continue
                except NoSuchElementException:
                    pass
                
                # Construct detail URL
                tender['detail_url'] = f"{SITE_BASE}/Tenders/Tenders_Detail?ProjectID={project_id}"
                
                if tender.get('title') or tender.get('project_id'):
                    tenders.append(tender)
                    
            except StaleElementReferenceException:
                continue
            except Exception as e:
                print(f"Error extracting tender card: {e}")
                continue
                
    except Exception as e:
        print(f"Error finding tender cards: {e}")
    
    return tenders


def click_next_page(driver):
    """Click the Next button and return True if successful"""
    try:
        # Try multiple selectors for the Next button
        next_selectors = ["#buttonNext", "#buttonNextBot", "button:contains('Next')", ".paging button:first-child"]
        
        for selector in next_selectors:
            try:
                if selector.startswith("#"):
                    next_button = driver.find_element(By.CSS_SELECTOR, selector)
                else:
                    next_button = driver.find_element(By.CSS_SELECTOR, selector)
                
                if next_button.is_displayed() and next_button.is_enabled():
                    class_attr = next_button.get_attribute("class") or ""
                    if "disabled" not in class_attr:
                        driver.execute_script("arguments[0].click();", next_button)
                        time.sleep(3)
                        return True
            except:
                continue
    except Exception as e:
        print(f"Could not click Next: {e}")
    return False


def get_pagination_info(driver):
    """Get total count from pagination"""
    try:
        selectors = ["#labelPage", "#labelPageBot", ".paging label"]
        for selector in selectors:
            try:
                label = driver.find_element(By.CSS_SELECTOR, selector)
                text = label.text.strip()
                match = re.search(r'of\s+(\d+)', text)
                if match:
                    return int(match.group(1))
            except:
                continue
    except:
        pass
    return 0


def extract_detail_page(driver, url, project_id):
    """Extract detailed information from a tender detail page"""
    details = {}
    
    try:
        driver.get(url)
        time.sleep(3)
        
        # Wait for page load
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)
        
        # Save first detail page for debugging
        if project_id == "first":
            with open('/workspace/detail_page.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            driver.save_screenshot('/workspace/detail_screenshot.png')
        
        # Extract all tables
        try:
            tables = driver.find_elements(By.TAG_NAME, "table")
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    try:
                        cells = row.find_elements(By.CSS_SELECTOR, "th, td")
                        if len(cells) >= 2:
                            label = cells[0].text.strip().replace(":", "").lower().replace(" ", "_")
                            value = cells[-1].text.strip()
                            if label and value and len(label) < 50 and label not in details:
                                details[f"detail_{label}"] = value
                    except:
                        continue
        except:
            pass
        
        # Extract box sections
        try:
            boxes = driver.find_elements(By.CSS_SELECTOR, ".box.box-theme, .box")
            for box in boxes:
                try:
                    header = box.find_element(By.CSS_SELECTOR, ".box-header")
                    header_text = header.text.strip()[:50]
                    body = box.find_element(By.CSS_SELECTOR, ".box-body")
                    body_text = body.text.strip()
                    
                    if header_text and body_text and len(body_text) > 10:
                        key = f"section_{header_text.lower().replace(' ', '_')[:25]}"
                        if key not in details:
                            details[key] = body_text[:1500]
                except:
                    continue
        except:
            pass
        
        # Get main content
        try:
            content = driver.find_element(By.CSS_SELECTOR, "#content-dmbc, .content-wrapper")
            details['page_content'] = content.text.strip()[:3000]
        except:
            pass
            
    except Exception as e:
        print(f"  Error: {e}")
    
    return details


def scrape_tenders():
    """Main scraping function"""
    print(f"Starting tender scrape at {datetime.now()}")
    print(f"Target URL: {BASE_URL}")
    
    driver = None
    all_tenders = []
    
    try:
        print("\nSetting up Chrome browser...")
        driver = setup_driver()
        
        print(f"\nNavigating to {BASE_URL}...")
        driver.get(BASE_URL)
        
        print("Waiting for tender content to load...")
        
        # Wait longer and check for content
        for attempt in range(5):
            time.sleep(3)
            
            # Check current URL
            current_url = driver.current_url
            print(f"  Current URL: {current_url}")
            
            # Check if we have tender content
            try:
                container = driver.find_element(By.ID, "containerProjects")
                if container:
                    print("  Found containerProjects!")
                    break
            except:
                pass
            
            # Check for tender cards
            cards = driver.find_elements(By.CSS_SELECTOR, "[data-timescalesid]")
            if cards:
                print(f"  Found {len(cards)} tender cards!")
                break
            
            print(f"  Attempt {attempt + 1}: Waiting for content...")
        
        # Take screenshot
        driver.save_screenshot('/workspace/page_screenshot.png')
        print("Saved screenshot")
        
        # Save HTML
        with open('/workspace/rendered_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("Saved HTML")
        
        # Get pagination info
        total = get_pagination_info(driver)
        print(f"Total tenders: {total}")
        
        # Extract tenders
        page_num = 1
        seen_ids = set()
        
        while True:
            print(f"\n--- Page {page_num} ---")
            
            tenders = extract_tenders_from_listing(driver)
            print(f"Extracted {len(tenders)} tenders")
            
            new_count = 0
            for t in tenders:
                pid = t.get('project_id')
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_tenders.append(t)
                    new_count += 1
            
            print(f"New unique tenders: {new_count}")
            
            if not click_next_page(driver):
                print("No more pages")
                break
            
            page_num += 1
            if page_num > 10:
                break
        
        print(f"\nTotal unique tenders: {len(all_tenders)}")
        
        # Fetch detail pages
        if all_tenders:
            print("\n" + "="*50)
            print("Fetching detail pages...")
            print("="*50)
            
            for i, tender in enumerate(all_tenders):
                detail_url = tender.get('detail_url')
                if detail_url:
                    title = tender.get('title', 'Unknown')[:50]
                    print(f"\n[{i+1}/{len(all_tenders)}] {title}...")
                    
                    pid = "first" if i == 0 else tender.get('project_id', str(i))
                    details = extract_detail_page(driver, detail_url, pid)
                    tender.update(details)
                    
                    time.sleep(2)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
    
    return all_tenders


def save_to_csv(tenders, filename='/workspace/tenders.csv'):
    """Save tenders to CSV file"""
    if not tenders:
        print("No tenders to save")
        return
    
    all_keys = set()
    for tender in tenders:
        all_keys.update(tender.keys())
    
    fieldnames = sorted(list(all_keys))
    priority_cols = ['title', 'reference', 'process', 'deadline', 'project_id', 'detail_url']
    for col in reversed(priority_cols):
        if col in fieldnames:
            fieldnames.remove(col)
            fieldnames.insert(0, col)
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for tender in tenders:
            cleaned = {}
            for k, v in tender.items():
                if isinstance(v, str):
                    v = ' '.join(v.split())
                cleaned[k] = v
            writer.writerow(cleaned)
    
    print(f"\nSaved {len(tenders)} tenders to {filename}")


def save_to_json(tenders, filename='/workspace/tenders.json'):
    """Save tenders to JSON file"""
    cleaned = []
    for tender in tenders:
        c = {}
        for k, v in tender.items():
            if isinstance(v, str):
                v = ' '.join(v.split())
            c[k] = v
        cleaned.append(c)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(tenders)} tenders to {filename}")


if __name__ == "__main__":
    print("=" * 60)
    print("GGGI Tender Scraper")
    print("=" * 60)
    
    tenders = scrape_tenders()
    
    if tenders:
        save_to_csv(tenders)
        save_to_json(tenders)
        
        print("\n" + "=" * 60)
        print("SCRAPING COMPLETED!")
        print(f"Total tenders: {len(tenders)}")
        print("Files: tenders.csv, tenders.json")
        print("=" * 60)
        
        print("\nTenders found:")
        for i, t in enumerate(tenders, 1):
            print(f"\n{i}. {t.get('title', 'N/A')[:70]}")
            print(f"   Ref: {t.get('reference', 'N/A')} | Deadline: {t.get('deadline', 'N/A')[:30]}")
    else:
        print("\nNo tenders found. Check screenshots and HTML files.")
