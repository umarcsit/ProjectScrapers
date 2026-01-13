#!/usr/bin/env python3
"""
GGGI Tender Scraper
Scrapes current tenders from https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
using Selenium to handle JavaScript rendering, and saves them to a CSV file.
"""

import csv
import re
import time
from datetime import datetime
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class GGGITenderScraper:
    """Scraper for GGGI tender listings using Selenium."""
    
    BASE_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Current"
    PORTAL_BASE = "https://in-tendhost.co.uk/gggi/aspx"
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
    
    def _setup_driver(self):
        """Initialize Chrome WebDriver."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception:
            self.driver = webdriver.Chrome(options=chrome_options)
        
        self.driver.set_page_load_timeout(60)
    
    def _close_driver(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def fetch_page(self) -> bool:
        """Navigate to the tender page and wait for content to load."""
        try:
            print(f"Loading {self.BASE_URL}...")
            self.driver.get(self.BASE_URL)
            
            time.sleep(3)
            
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.ID, "containerProjects"))
                )
                print("Page loaded successfully.")
                return True
            except TimeoutException:
                print("Timeout waiting for content...")
                time.sleep(5)
                return True
                
        except Exception as e:
            print(f"Error loading page: {e}")
            return False
    
    def parse_tenders(self) -> List[Dict[str, str]]:
        """Extract tender information from the loaded page."""
        tenders = []
        seen_ids = set()
        
        time.sleep(2)
        
        # Find elements with data-timescalesid - these are the main tender containers
        try:
            tender_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-timescalesid]")
            print(f"Found {len(tender_elements)} tender elements with IDs")
        except Exception as e:
            print(f"Error finding tender elements: {e}")
            return []
        
        for element in tender_elements:
            try:
                tender_id = element.get_attribute("data-timescalesid")
                
                # Skip duplicates
                if tender_id in seen_ids:
                    continue
                seen_ids.add(tender_id)
                
                tender = self._extract_tender_data(element, tender_id)
                if tender and tender.get('Title') and tender['Title'] != 'View Details':
                    tenders.append(tender)
                    
            except Exception as e:
                print(f"Error processing tender: {e}")
                continue
        
        return tenders
    
    def _extract_tender_data(self, element, tender_id: str) -> Optional[Dict[str, str]]:
        """Extract structured data from a tender element."""
        tender = {'ID': tender_id}
        
        # Get all text content
        text_content = element.text
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # Parse lines for specific fields
        for i, line in enumerate(lines):
            # Skip "View Details" lines
            if line == 'View Details':
                continue
                
            # Deadline/Closing date
            if 'Deadline For Applications' in line:
                match = re.search(r'(\d{1,2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2})', line)
                if match:
                    tender['Closing_Date'] = match.group(1)
            
            # Timezone info
            elif line.startswith('(UTC'):
                tender['Timezone'] = line.strip('()')
            
            # Title (explicit label)
            elif line.startswith('Title '):
                tender['Title'] = line.replace('Title ', '').strip()
            
            # Reference
            elif line.startswith('Reference '):
                tender['Reference'] = line.replace('Reference ', '').strip()
            
            # Process type
            elif line.startswith('Process '):
                tender['Process_Type'] = line.replace('Process ', '').strip()
            
            # Category
            elif line.startswith('Category '):
                tender['Category'] = line.replace('Category ', '').strip()
        
        # If Title not found from label, use first line that's not a metadata line
        if not tender.get('Title'):
            for line in lines:
                if not any(line.startswith(prefix) for prefix in 
                          ['Deadline', 'Title ', 'Reference ', 'Process ', 'Category ', '(UTC', 'View']):
                    tender['Title'] = line
                    break
        
        # Construct the detail link
        tender['Link'] = f"{self.PORTAL_BASE}/ProjectManage/{tender_id}"
        
        return tender if tender.get('Title') else None
    
    def save_to_csv(self, tenders: List[Dict[str, str]], filename: str = None) -> str:
        """Save tender data to CSV file."""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'gggi_tenders_{timestamp}.csv'
        
        if not tenders:
            print("No tenders to save.")
            return filename
        
        # Define column order
        columns = ['ID', 'Title', 'Reference', 'Process_Type', 'Category', 
                   'Closing_Date', 'Timezone', 'Link']
        
        # Only include columns that have data
        columns = [col for col in columns if any(t.get(col) for t in tenders)]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()
            for tender in tenders:
                row = {k: v for k, v in tender.items() if k in columns}
                writer.writerow(row)
        
        print(f"Saved {len(tenders)} tenders to {filename}")
        return filename
    
    def scrape(self, output_file: str = None) -> List[Dict[str, str]]:
        """Main scraping method."""
        print("="*60)
        print("GGGI Tender Scraper")
        print("="*60)
        
        try:
            self._setup_driver()
            
            if not self.fetch_page():
                print("Failed to load page.")
                return []
            
            print("Extracting tender information...")
            tenders = self.parse_tenders()
            
            print(f"Found {len(tenders)} unique tenders.")
            
            if tenders:
                self.save_to_csv(tenders, output_file)
            
            return tenders
            
        finally:
            self._close_driver()


def main():
    """Main entry point."""
    scraper = GGGITenderScraper(headless=True)
    tenders = scraper.scrape(output_file='gggi_tenders.csv')
    
    if tenders:
        print("\n" + "="*60)
        print("EXTRACTED TENDER DATA")
        print("="*60)
        
        for i, tender in enumerate(tenders, 1):
            print(f"\n--- Tender {i} ---")
            print(f"  ID: {tender.get('ID', 'N/A')}")
            title = tender.get('Title', 'N/A')
            print(f"  Title: {title[:70]}{'...' if len(title) > 70 else ''}")
            print(f"  Reference: {tender.get('Reference', 'N/A')}")
            print(f"  Process: {tender.get('Process_Type', 'N/A')}")
            print(f"  Closing Date: {tender.get('Closing_Date', 'N/A')}")
            print(f"  Link: {tender.get('Link', 'N/A')}")
            
        print("\n" + "="*60)
        print(f"✓ Total: {len(tenders)} tenders saved to gggi_tenders.csv")
        print("="*60)
    else:
        print("\nNo tenders found on the page.")


if __name__ == "__main__":
    main()
