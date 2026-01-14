#!/usr/bin/env python3
"""
Pakistan Tender Scraper - PPRA Notice Tenders
Scrapes tender information from PPRA (Public Procurement Regulatory Authority) Pakistan
Website: https://ppra.gov.pk/#/tenders/NoticeTenders

Features:
- Extracts tender listings with all available fields
- Handles pagination
- Configurable MAX_RECORDS variable
- Exports to CSV with all columns
"""

import time
import re
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd

# ============================================================
# CONFIGURATION - Adjust MAX_RECORDS as needed
# ============================================================
BASE_URL = "https://ppra.gov.pk/#/tenders/NoticeTenders"
MAX_RECORDS = 50  # Maximum records to scrape. Set to None for ALL.
OUTPUT_CSV = "tenders_data.csv"
# ============================================================


class PPRATenderScraper:
    """PPRA Tender Scraper"""
    
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.tenders = []
        self.total_records = 0
        
    def setup_driver(self):
        """Initialize Chrome WebDriver"""
        print("Initializing browser...")
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        self.driver = uc.Chrome(options=options, version_main=143)
        self.driver.set_page_load_timeout(60)
        print("✓ Browser ready")
        
    def close_driver(self):
        """Close browser"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            print("✓ Browser closed")
            
    def wait_for_data(self, timeout=30):
        """Wait for table data"""
        for i in range(timeout):
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells and cells[0].text.strip().isdigit():
                        return True
            except:
                pass
            time.sleep(1)
        return False
        
    def get_total_pages(self):
        """Get total number of pages"""
        try:
            # Look for page numbers
            page_links = self.driver.find_elements(By.CSS_SELECTOR, ".pagination .page-link")
            page_nums = []
            for link in page_links:
                text = link.text.strip()
                if text.isdigit():
                    page_nums.append(int(text))
            if page_nums:
                return max(page_nums)
        except:
            pass
        return 1
        
    def extract_tenders(self):
        """Extract tender rows from current page"""
        tenders = []
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if not cells or len(cells) < 4:
                        continue
                    
                    # Get raw values
                    tender_no_raw = cells[1].text.strip() if len(cells) > 1 else ''
                    details_raw = cells[2].text.strip() if len(cells) > 2 else ''
                    
                    # Parse tender number (remove "View Invoice")
                    tender_no = tender_no_raw.replace('View Invoice', '').strip()
                    
                    # Parse details: "Organization,Location | Title | Description"
                    details_parts = details_raw.split('\n')
                    organization = ''
                    title = ''
                    description = ''
                    
                    if len(details_parts) >= 1:
                        org_part = details_parts[0]
                        if ',' in org_part:
                            org_split = org_part.rsplit(',', 1)
                            organization = org_split[0].strip()
                        else:
                            organization = org_part.strip()
                            
                    if len(details_parts) >= 2:
                        title = details_parts[1].strip()
                        
                    if len(details_parts) >= 3:
                        description = ' '.join(details_parts[2:]).strip()
                    else:
                        description = title  # Use title as description if no separate desc
                        
                    tender = {
                        'SR_No': cells[0].text.strip() if len(cells) > 0 else '',
                        'Tender_No': tender_no,
                        'Organization': organization,
                        'Title': title,
                        'Description': description,
                        'Downloads': cells[3].text.strip() if len(cells) > 3 else '',
                        'Advertisement_Date': cells[4].text.strip() if len(cells) > 4 else '',
                        'Closing_Date': cells[5].text.strip() if len(cells) > 5 else '',
                    }
                    
                    # Get download links
                    try:
                        links = row.find_elements(By.TAG_NAME, "a")
                        for link in links:
                            href = link.get_attribute('href')
                            if href and 'javascript' not in href:
                                tender['Download_URL'] = href
                                break
                    except:
                        pass
                        
                    if tender['SR_No']:
                        tenders.append(tender)
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error extracting: {e}")
            
        return tenders
        
    def go_next_page(self):
        """Go to next page"""
        try:
            next_links = self.driver.find_elements(By.CSS_SELECTOR, ".pagination .page-link")
            for link in next_links:
                if 'Next' in link.text:
                    # Check if disabled
                    parent = link.find_element(By.XPATH, "./..")
                    if 'disabled' in (parent.get_attribute('class') or ''):
                        return False
                    self.driver.execute_script("arguments[0].click();", link)
                    time.sleep(3)
                    return self.wait_for_data(15)
        except:
            pass
        return False
        
    def scrape(self, max_records=MAX_RECORDS):
        """Main scrape method"""
        print("\n" + "="*60)
        print("PPRA PAKISTAN TENDER SCRAPER")
        print("="*60)
        print(f"URL: {BASE_URL}")
        print(f"MAX_RECORDS: {max_records if max_records else 'ALL'}")
        print("="*60)
        
        self.setup_driver()
        
        try:
            # Navigate to page
            print(f"\nLoading {BASE_URL}...")
            self.driver.get(BASE_URL)
            time.sleep(8)
            
            if not self.wait_for_data(40):
                print("✗ Failed to load data")
                return []
                
            print("✓ Page loaded successfully")
            
            # Get pagination info
            total_pages = self.get_total_pages()
            print(f"\n📊 Total pages found: {total_pages}")
            print(f"📊 Estimated total records: ~{total_pages * 10}")
            self.total_records = total_pages * 10
            
            # Scrape pages
            page = 1
            scraped = 0
            
            while True:
                print(f"\n--- Page {page} ---")
                
                page_tenders = self.extract_tenders()
                print(f"Found {len(page_tenders)} tenders")
                
                for tender in page_tenders:
                    if max_records and scraped >= max_records:
                        print(f"\n✓ Reached MAX_RECORDS: {max_records}")
                        break
                        
                    tender['Page'] = page
                    tender['Scrape_Date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.tenders.append(tender)
                    scraped += 1
                    print(f"  [{scraped}] {tender['Tender_No'][:30]}...")
                    
                if max_records and scraped >= max_records:
                    break
                    
                # Try next page
                if page >= total_pages:
                    print("\nReached last page")
                    break
                    
                if not self.go_next_page():
                    print("\nNo more pages")
                    break
                    
                page += 1
                if page > 20:  # Safety limit
                    break
                    
            print("\n" + "="*60)
            print("SCRAPING COMPLETE")
            print("="*60)
            print(f"📊 Total available: ~{self.total_records}")
            print(f"✓ Records scraped: {scraped}")
            
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            self.close_driver()
            
        return self.tenders
        
    def save_csv(self, filename=OUTPUT_CSV):
        """Save to CSV"""
        if not self.tenders:
            print("No data to save")
            return False
            
        df = pd.DataFrame(self.tenders)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print(f"\n✓ Saved: {filename}")
        print(f"  Records: {len(df)}")
        print(f"  Columns: {list(df.columns)}")
        
        return True


def main():
    """Main function"""
    scraper = PPRATenderScraper(headless=True)
    tenders = scraper.scrape(max_records=MAX_RECORDS)
    
    if tenders:
        scraper.save_csv(OUTPUT_CSV)
        
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"📊 TOTAL AVAILABLE: ~{scraper.total_records} records")
        print(f"✓ SCRAPED: {len(tenders)} records") 
        print(f"📁 OUTPUT: {OUTPUT_CSV}")
        print("="*60)
        
        print("\nSample data:")
        for i, t in enumerate(tenders[:3], 1):
            print(f"\n{i}. {t.get('Tender_No', 'N/A')}")
            details = t.get('Tender_Details', '')[:80]
            print(f"   {details}...")
            print(f"   Closing: {t.get('Closing_Date', 'N/A')}")
            
    return scraper.total_records, len(tenders) if tenders else 0


if __name__ == "__main__":
    total, scraped = main()
    print(f"\n{'='*60}")
    print(f"RESULT: Scraped {scraped} records (Total available: ~{total})")
    print(f"MAX_RECORDS variable is set to: {MAX_RECORDS}")
    print(f"{'='*60}")
