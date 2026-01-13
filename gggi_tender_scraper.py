#!/usr/bin/env python3
"""
GGGI Tender Scraper - Full Data Extraction
Scrapes current tenders from https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
Clicks on each tender to extract detailed information.
Exports all data to CSV.
"""

import csv
import os
import re
import time
from datetime import datetime
from dataclasses import dataclass, fields, asdict
from typing import List, Optional, Dict
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager


@dataclass
class Tender:
    """Complete tender information."""
    # Basic Info from List
    title: str = ""
    reference: str = ""
    process_type: str = ""
    timezone: str = ""
    issue_date: str = ""
    deadline: str = ""
    
    # Detail Page Info
    status: str = ""
    buyer: str = ""
    buyer_contact: str = ""
    buyer_email: str = ""
    buyer_phone: str = ""
    category: str = ""
    cpv_codes: str = ""
    location: str = ""
    region: str = ""
    country: str = ""
    estimated_value: str = ""
    currency: str = ""
    duration: str = ""
    
    # Description
    description: str = ""
    scope_of_work: str = ""
    eligibility: str = ""
    submission_requirements: str = ""
    evaluation_criteria: str = ""
    
    # Documents
    documents: str = ""
    attachments: str = ""
    
    # URLs
    detail_url: str = ""
    project_id: str = ""
    
    # Additional
    additional_info: str = ""
    questions_deadline: str = ""
    site_visit: str = ""


class GGGITenderScraper:
    """Full scraper for GGGI tenders with detail page extraction."""
    
    BASE_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Current"
    
    def __init__(self, email: str = None, password: str = None, headless: bool = True):
        self.email = email or os.environ.get('GGGI_EMAIL')
        self.password = password or os.environ.get('GGGI_PASSWORD')
        self.headless = headless
        self.driver = None
        self.wait = None
    
    def _setup_driver(self):
        """Set up Selenium WebDriver."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
    
    def _close_driver(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def parse_tender_tables(self, soup) -> List[Dict]:
        """Parse tender info from the table pairs on listing page."""
        tables = soup.find_all('table')
        tenders = []
        
        i = 0
        while i < len(tables) - 1:
            tender_data = {}
            
            # Parse basic info table
            basic_table = tables[i]
            for row in basic_table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[-1].get_text(strip=True)
                    
                    if 'title' in label:
                        tender_data['title'] = value
                    elif 'reference' in label:
                        tender_data['reference'] = value
                    elif 'process' in label:
                        tender_data['process_type'] = value
            
            if not tender_data.get('title') and not tender_data.get('reference'):
                i += 1
                continue
            
            # Parse date info table (next table)
            if i + 1 < len(tables):
                date_table = tables[i + 1]
                for row in date_table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[-1].get_text(strip=True)
                        
                        if 'timezone' in label:
                            tender_data['timezone'] = value
                        elif 'issue' in label:
                            tender_data['issue_date'] = value
                        elif 'deadline' in label:
                            tender_data['deadline'] = value
            
            tenders.append(tender_data)
            i += 2
        
        return tenders
    
    def get_project_ids(self) -> List[str]:
        """Extract project IDs from the page buttons."""
        project_ids = []
        buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[onclick*='ProjectManage']")
        
        for button in buttons:
            onclick = button.get_attribute('onclick') or ''
            match = re.search(r'ProjectManage\((\d+)\)', onclick)
            if match:
                project_ids.append(match.group(1))
        
        return project_ids
    
    def click_next_page(self) -> bool:
        """Click next page button if available."""
        try:
            # Look for Next button
            next_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Next')] | //a[contains(text(), 'Next')] | //*[contains(@class, 'next')]")
            for btn in next_buttons:
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    time.sleep(3)
                    return True
        except Exception:
            pass
        return False
    
    def extract_detail_page(self, project_id: str) -> Dict:
        """Click on a tender and extract detail page information."""
        details = {}
        
        try:
            # Click the button to open detail page
            button = self.driver.find_element(By.CSS_SELECTOR, f"button[onclick*='ProjectManage({project_id})']")
            
            # Scroll to button
            self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            time.sleep(0.5)
            
            # Click
            try:
                button.click()
            except ElementClickInterceptedException:
                self.driver.execute_script("arguments[0].click();", button)
            
            time.sleep(3)
            
            # Parse the detail page
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            page_text = self.driver.find_element(By.TAG_NAME, 'body').text
            
            # Extract all labeled fields
            for table in soup.find_all('table'):
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[-1].get_text(strip=True)
                        
                        if value and value.lower() not in ['n/a', '-', '']:
                            self._map_detail_field(details, label, value)
            
            # Extract from definition lists
            for dt in soup.find_all('dt'):
                try:
                    label = dt.get_text(strip=True).lower()
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        value = dd.get_text(strip=True)
                        self._map_detail_field(details, label, value)
                except:
                    pass
            
            # Look for description sections
            desc_patterns = [
                (r'description[:\s]*(.+?)(?=\n\n|\Z)', 'description'),
                (r'scope[:\s]*(.+?)(?=\n\n|\Z)', 'scope_of_work'),
                (r'eligibility[:\s]*(.+?)(?=\n\n|\Z)', 'eligibility'),
                (r'submission[:\s]*(.+?)(?=\n\n|\Z)', 'submission_requirements'),
                (r'evaluation[:\s]*(.+?)(?=\n\n|\Z)', 'evaluation_criteria'),
            ]
            
            for pattern, field in desc_patterns:
                if not details.get(field):
                    match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
                    if match:
                        details[field] = match.group(1).strip()[:2000]
            
            # Extract documents/attachments
            doc_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if any(ext in href.lower() for ext in ['.pdf', '.doc', '.xls', '.zip', 'download', 'attachment', 'document']):
                    doc_name = link.get_text(strip=True) or 'Document'
                    doc_links.append(f"{doc_name}")
            
            if doc_links:
                details['documents'] = ' | '.join(doc_links[:20])
            
            # Go back to listing
            self.driver.back()
            time.sleep(2)
            
        except Exception as e:
            print(f"    Error extracting details for project {project_id}: {e}")
            # Try to go back anyway
            try:
                self.driver.get(self.BASE_URL)
                time.sleep(3)
            except:
                pass
        
        details['project_id'] = project_id
        return details
    
    def _map_detail_field(self, details: Dict, label: str, value: str):
        """Map a label to the appropriate detail field."""
        label = label.lower().strip()
        
        mappings = {
            'status': ['status', 'state', 'stage'],
            'buyer': ['buyer', 'contracting authority', 'organization', 'organisation', 'client', 'authority'],
            'buyer_contact': ['contact', 'contact person', 'contact name', 'officer'],
            'buyer_email': ['email', 'e-mail'],
            'buyer_phone': ['phone', 'telephone', 'tel', 'mobile'],
            'category': ['category', 'type', 'sector', 'classification'],
            'cpv_codes': ['cpv', 'cpv code'],
            'location': ['location', 'place', 'delivery location', 'place of delivery', 'address'],
            'region': ['region', 'area', 'territory', 'district'],
            'country': ['country', 'nation'],
            'estimated_value': ['value', 'estimated value', 'contract value', 'budget', 'amount', 'cost'],
            'currency': ['currency'],
            'duration': ['duration', 'period', 'contract period', 'length'],
            'description': ['description', 'summary', 'brief', 'overview'],
            'scope_of_work': ['scope', 'scope of work', 'terms of reference', 'tor'],
            'eligibility': ['eligibility', 'qualification', 'requirements'],
            'questions_deadline': ['questions', 'clarification', 'query deadline'],
            'site_visit': ['site visit', 'pre-bid'],
        }
        
        for field, keywords in mappings.items():
            if any(kw in label for kw in keywords):
                if not details.get(field):
                    details[field] = value
                break
    
    def scrape(self) -> List[Tender]:
        """Main scraping method."""
        tenders = []
        
        try:
            self._setup_driver()
            
            print(f"Loading {self.BASE_URL}...")
            self.driver.get(self.BASE_URL)
            time.sleep(8)
            
            # Scroll to load content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            all_tender_data = []
            all_project_ids = []
            page_num = 1
            
            while True:
                print(f"\nProcessing page {page_num}...")
                
                # Parse current page
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                page_tenders = self.parse_tender_tables(soup)
                page_ids = self.get_project_ids()
                
                print(f"  Found {len(page_tenders)} tenders, {len(page_ids)} project IDs")
                
                # Combine tender data with project IDs
                for i, tender_data in enumerate(page_tenders):
                    if i < len(page_ids):
                        tender_data['project_id'] = page_ids[i]
                    all_tender_data.append(tender_data)
                
                all_project_ids.extend(page_ids)
                
                # Try to go to next page
                if not self.click_next_page():
                    break
                page_num += 1
                if page_num > 10:  # Safety limit
                    break
            
            print(f"\nTotal tenders found: {len(all_tender_data)}")
            print(f"Total project IDs: {len(all_project_ids)}")
            
            # Now extract details for each tender
            print("\nExtracting detail page information...")
            
            for i, tender_data in enumerate(all_tender_data):
                project_id = tender_data.get('project_id', '')
                title = tender_data.get('title', tender_data.get('reference', 'Unknown'))[:50]
                
                print(f"\n[{i+1}/{len(all_tender_data)}] {title}")
                
                if project_id:
                    # Reload listing page if needed
                    if 'Tenders/Current' not in self.driver.current_url:
                        self.driver.get(self.BASE_URL)
                        time.sleep(5)
                    
                    # Extract details
                    detail_data = self.extract_detail_page(project_id)
                    
                    # Merge data
                    for key, value in detail_data.items():
                        if value and not tender_data.get(key):
                            tender_data[key] = value
                
                # Create Tender object
                tender = Tender(
                    title=tender_data.get('title', ''),
                    reference=tender_data.get('reference', ''),
                    process_type=tender_data.get('process_type', ''),
                    timezone=tender_data.get('timezone', ''),
                    issue_date=tender_data.get('issue_date', ''),
                    deadline=tender_data.get('deadline', ''),
                    status=tender_data.get('status', ''),
                    buyer=tender_data.get('buyer', ''),
                    buyer_contact=tender_data.get('buyer_contact', ''),
                    buyer_email=tender_data.get('buyer_email', ''),
                    buyer_phone=tender_data.get('buyer_phone', ''),
                    category=tender_data.get('category', ''),
                    cpv_codes=tender_data.get('cpv_codes', ''),
                    location=tender_data.get('location', ''),
                    region=tender_data.get('region', ''),
                    country=tender_data.get('country', ''),
                    estimated_value=tender_data.get('estimated_value', ''),
                    currency=tender_data.get('currency', ''),
                    duration=tender_data.get('duration', ''),
                    description=tender_data.get('description', ''),
                    scope_of_work=tender_data.get('scope_of_work', ''),
                    eligibility=tender_data.get('eligibility', ''),
                    submission_requirements=tender_data.get('submission_requirements', ''),
                    evaluation_criteria=tender_data.get('evaluation_criteria', ''),
                    documents=tender_data.get('documents', ''),
                    attachments=tender_data.get('attachments', ''),
                    detail_url=tender_data.get('detail_url', ''),
                    project_id=tender_data.get('project_id', ''),
                    additional_info=tender_data.get('additional_info', ''),
                    questions_deadline=tender_data.get('questions_deadline', ''),
                    site_visit=tender_data.get('site_visit', '')
                )
                
                tenders.append(tender)
            
            return tenders
            
        finally:
            self._close_driver()
    
    def save_to_csv(self, tenders: List[Tender], filename: str = None) -> str:
        """Save tenders to CSV."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gggi_tenders_{timestamp}.csv"
        
        fieldnames = [f.name for f in fields(Tender)]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for tender in tenders:
                writer.writerow(asdict(tender))
        
        print(f"\nSaved {len(tenders)} tenders to {filename}")
        return filename


def main():
    """Main entry point."""
    print("="*70)
    print("GGGI Tender Scraper - Full Data Extraction")
    print("="*70)
    
    scraper = GGGITenderScraper(headless=True)
    tenders = scraper.scrape()
    
    if tenders:
        print("\n" + "="*70)
        print("TENDER SUMMARY")
        print("="*70)
        
        for i, tender in enumerate(tenders, 1):
            print(f"\n{i}. {tender.title[:70]}...")
            print(f"   Reference: {tender.reference}")
            print(f"   Process: {tender.process_type}")
            print(f"   Issue Date: {tender.issue_date}")
            print(f"   Deadline: {tender.deadline}")
            if tender.buyer:
                print(f"   Buyer: {tender.buyer}")
            if tender.estimated_value:
                print(f"   Value: {tender.estimated_value}")
            if tender.description:
                print(f"   Description: {tender.description[:100]}...")
            if tender.documents:
                print(f"   Documents: {tender.documents[:100]}...")
        
        csv_file = scraper.save_to_csv(tenders)
        
        print(f"\n{'='*70}")
        print(f"Results exported to: {csv_file}")
        print(f"Total tenders: {len(tenders)}")
        print(f"Total columns: {len(fields(Tender))}")
        
        # List all columns
        print(f"\nColumns in CSV:")
        for f in fields(Tender):
            print(f"  - {f.name}")
    else:
        print("\nNo tenders found.")


if __name__ == "__main__":
    main()
