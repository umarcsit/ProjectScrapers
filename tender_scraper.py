#!/usr/bin/env python3
"""
PPRA Pakistan - COMPREHENSIVE Tender Scraper
Scrapes ALL tender sections from PPRA website

Sections:
- Active Tenders
- Notice Tenders  
- Pre-Qualifications (PQ)
- Request for Proposal (RFP)
- Expression of Interest (EOI)
- Sales/Auction/Disposal (SAD)
- Works, Goods, Services categories
- Tenders History
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
# CONFIGURATION
# ============================================================
MAX_RECORDS = 500  # Maximum total records to scrape (None for ALL)
MAX_PER_SECTION = 100  # Max records per section
OUTPUT_CSV = "tenders_data.csv"
# ============================================================

# All PPRA tender sections to scrape
TENDER_SECTIONS = [
    ("Active Tenders", "https://ppra.gov.pk/#/tenders/activetenders"),
    ("Tenders History", "https://ppra.gov.pk/#/tenders/tendershistory"),
    ("Notice Tenders", "https://ppra.gov.pk/#/tenders/NoticeTenders"),
    ("Pre-Qualifications", "https://ppra.gov.pk/#/tenders/PQTenders"),
    ("Request for Proposal", "https://ppra.gov.pk/#/tenders/RFPTenders"),
    ("Expression of Interest", "https://ppra.gov.pk/#/tenders/EOITenders"),
    ("Sales/Auction/Disposal", "https://ppra.gov.pk/#/tenders/SADTenders"),
    ("Works", "https://ppra.gov.pk/#/tenders/type/Works"),
    ("Goods", "https://ppra.gov.pk/#/tenders/type/Goods"),
    ("Services", "https://ppra.gov.pk/#/tenders/type/Services"),
]


class PPRAComprehensiveScraper:
    """Comprehensive PPRA Tender Scraper - All Sections"""
    
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.all_tenders = []
        self.section_counts = {}
        self.total_available = 0
        
    def setup_driver(self):
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
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            print("✓ Browser closed")
            
    def wait_for_data(self, timeout=20):
        """Wait for table data to load"""
        for i in range(timeout):
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells and len(cells) >= 2:
                        text = cells[0].text.strip()
                        if text and (text.isdigit() or text.startswith('TS')):
                            return True
            except:
                pass
            time.sleep(1)
        return False
        
    def get_page_count(self):
        """Get number of pages available"""
        try:
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
        
    def get_total_from_page(self):
        """Try to extract total count from page"""
        try:
            page_source = self.driver.page_source
            patterns = [
                r'of\s+([\d,]+)\s+entries',
                r'Total[:\s]+([\d,]+)',
                r'([\d,]+)\s+records?',
                r'([\d,]+)\s+results?'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                for m in matches:
                    num = int(m.replace(',', ''))
                    if num > 5:
                        return num
        except:
            pass
        return 0
        
    def extract_tenders(self, section_name):
        """Extract tenders from current page"""
        tenders = []
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if not cells or len(cells) < 2:
                        continue
                    
                    # Extract data based on number of columns
                    tender = {'Section': section_name}
                    
                    for i, cell in enumerate(cells):
                        text = cell.text.strip().replace('\n', ' | ')
                        if i == 0:
                            tender['SR_No'] = text
                        elif i == 1:
                            # Parse tender number
                            tender['Tender_No'] = text.replace('View Invoice', '').strip()
                        elif i == 2:
                            # Parse details - Organization | Title | Description
                            parts = text.split(' | ')
                            if len(parts) >= 1:
                                tender['Organization'] = parts[0].strip()
                            if len(parts) >= 2:
                                tender['Title'] = parts[1].strip()
                            if len(parts) >= 3:
                                tender['Description'] = ' '.join(parts[2:]).strip()
                            else:
                                tender['Description'] = parts[-1].strip() if parts else ''
                        elif i == 3:
                            tender['Downloads'] = text
                        elif i == 4:
                            tender['Advertisement_Date'] = text
                        elif i == 5:
                            tender['Closing_Date'] = text
                        else:
                            tender[f'Column_{i+1}'] = text
                            
                    if tender.get('SR_No') or tender.get('Tender_No'):
                        tender['Scrape_Date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        tenders.append(tender)
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            pass
            
        return tenders
        
    def go_next_page(self):
        """Navigate to next page"""
        try:
            next_links = self.driver.find_elements(By.CSS_SELECTOR, ".pagination .page-link")
            for link in next_links:
                if 'Next' in link.text:
                    parent = link.find_element(By.XPATH, "./..")
                    if 'disabled' in (parent.get_attribute('class') or ''):
                        return False
                    self.driver.execute_script("arguments[0].click();", link)
                    time.sleep(3)
                    return self.wait_for_data(10)
        except:
            pass
        return False
        
    def scrape_section(self, name, url, max_records=MAX_PER_SECTION):
        """Scrape a single section"""
        section_tenders = []
        
        print(f"\n{'='*50}")
        print(f"📂 {name}")
        print(f"   {url}")
        print('='*50)
        
        try:
            self.driver.get(url)
            time.sleep(5)
            
            if not self.wait_for_data(15):
                print("   ⚠ No data found in this section")
                return []
                
            # Get page count and estimate
            pages = self.get_page_count()
            total_estimate = self.get_total_from_page()
            
            rows_first_page = len(self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr"))
            if total_estimate == 0:
                total_estimate = pages * rows_first_page
                
            print(f"   📊 Pages: {pages}")
            print(f"   📊 Estimated records: ~{total_estimate}")
            self.section_counts[name] = total_estimate
            self.total_available += total_estimate
            
            # Scrape pages
            page = 1
            scraped = 0
            
            while True:
                print(f"   Page {page}...", end=" ")
                
                tenders = self.extract_tenders(name)
                print(f"found {len(tenders)} tenders")
                
                for tender in tenders:
                    if max_records and scraped >= max_records:
                        break
                    section_tenders.append(tender)
                    scraped += 1
                    
                if max_records and scraped >= max_records:
                    print(f"   ✓ Reached section limit: {max_records}")
                    break
                    
                if page >= pages:
                    break
                    
                if not self.go_next_page():
                    break
                    
                page += 1
                if page > 20:  # Safety limit per section
                    break
                    
            print(f"   ✓ Scraped {len(section_tenders)} from {name}")
            
        except Exception as e:
            print(f"   ✗ Error: {e}")
            
        return section_tenders
        
    def scrape_all(self, max_total=MAX_RECORDS):
        """Scrape all sections"""
        print("\n" + "="*70)
        print("PPRA PAKISTAN - COMPREHENSIVE TENDER SCRAPER")
        print("="*70)
        print(f"Sections to scrape: {len(TENDER_SECTIONS)}")
        print(f"MAX_RECORDS: {max_total if max_total else 'ALL'}")
        print(f"MAX_PER_SECTION: {MAX_PER_SECTION}")
        print("="*70)
        
        self.setup_driver()
        
        try:
            total_scraped = 0
            
            for name, url in TENDER_SECTIONS:
                if max_total and total_scraped >= max_total:
                    print(f"\n✓ Reached MAX_RECORDS limit: {max_total}")
                    break
                    
                # Calculate remaining allowance
                remaining = (max_total - total_scraped) if max_total else MAX_PER_SECTION
                section_limit = min(remaining, MAX_PER_SECTION)
                
                section_tenders = self.scrape_section(name, url, section_limit)
                self.all_tenders.extend(section_tenders)
                total_scraped += len(section_tenders)
                
            print("\n" + "="*70)
            print("SCRAPING COMPLETE")
            print("="*70)
            
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            self.close_driver()
            
        return self.all_tenders
        
    def save_csv(self, filename=OUTPUT_CSV):
        """Save all tenders to CSV"""
        if not self.all_tenders:
            print("No data to save")
            return False
            
        df = pd.DataFrame(self.all_tenders)
        
        # Order columns
        priority = ['Section', 'SR_No', 'Tender_No', 'Organization', 'Title', 
                   'Description', 'Advertisement_Date', 'Closing_Date', 
                   'Downloads', 'Scrape_Date']
        cols = [c for c in priority if c in df.columns]
        cols += [c for c in df.columns if c not in cols]
        df = df[cols]
        
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print(f"\n✓ Saved: {filename}")
        print(f"  Total records: {len(df)}")
        print(f"  Columns: {len(df.columns)}")
        
        return True
        
    def print_summary(self):
        """Print final summary"""
        print("\n" + "="*70)
        print("📊 FINAL SUMMARY - TOTAL TENDERS AVAILABLE")
        print("="*70)
        
        print("\nBy Section:")
        for section, count in self.section_counts.items():
            print(f"  {section}: ~{count}")
            
        print(f"\n{'='*70}")
        print(f"📊 TOTAL AVAILABLE ON PPRA: ~{self.total_available} tenders")
        print(f"✓ TOTAL SCRAPED: {len(self.all_tenders)} tenders")
        print(f"📁 OUTPUT FILE: {OUTPUT_CSV}")
        print(f"{'='*70}")


def main():
    scraper = PPRAComprehensiveScraper(headless=True)
    tenders = scraper.scrape_all(max_total=MAX_RECORDS)
    
    if tenders:
        scraper.save_csv(OUTPUT_CSV)
        scraper.print_summary()
    else:
        print("\nNo tenders scraped")
        
    return scraper.total_available, len(tenders) if tenders else 0


if __name__ == "__main__":
    total, scraped = main()
    print(f"\n{'='*70}")
    print(f"RESULT: Scraped {scraped} tenders")
    print(f"TOTAL AVAILABLE ON PPRA: ~{total} tenders")
    print(f"MAX_RECORDS is set to: {MAX_RECORDS}")
    print(f"{'='*70}")
