#!/usr/bin/env python3
"""
GGGI Tender Scraper
Scrapes current tenders from https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
and exports them to a CSV file.

Note: This site requires authentication. You need to provide login credentials.
"""

import csv
import os
import time
from datetime import datetime
from dataclasses import dataclass, fields
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


@dataclass
class Tender:
    """Represents a tender listing."""
    title: str
    reference: Optional[str] = None
    deadline: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None


class GGGITenderScraper:
    """Scraper for GGGI tenders from in-tendhost.co.uk"""
    
    BASE_URL = "https://in-tendhost.co.uk/gggi/aspx/Tenders/Current"
    LOGIN_URL = "https://in-tendhost.co.uk/gggi"
    
    def __init__(self, email: str = None, password: str = None, headless: bool = True):
        self.email = email or os.environ.get('GGGI_EMAIL')
        self.password = password or os.environ.get('GGGI_PASSWORD')
        self.headless = headless
        self.driver = None
    
    def _setup_driver(self):
        """Set up Selenium WebDriver with Chrome."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
    
    def _close_driver(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def login(self) -> bool:
        """Login to the portal."""
        if not self.email or not self.password:
            print("ERROR: Login credentials not provided.")
            print("Please set GGGI_EMAIL and GGGI_PASSWORD environment variables")
            print("Or pass email and password to the constructor.")
            return False
        
        try:
            print(f"Navigating to login page...")
            self.driver.get(self.LOGIN_URL)
            time.sleep(2)
            
            # Find and fill email field
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[id*='email'], input[placeholder*='mail']"))
            )
            email_field.clear()
            email_field.send_keys(self.email)
            
            # Find and fill password field
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Find and click login button
            login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], button.login, button[class*='login']")
            login_btn.click()
            
            # Wait for login to complete
            time.sleep(3)
            
            # Check if login was successful (look for logout link or dashboard elements)
            if "login" not in self.driver.current_url.lower() or "dashboard" in self.driver.current_url.lower():
                print("Login successful!")
                return True
            else:
                print("Login may have failed. Current URL:", self.driver.current_url)
                return False
                
        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    def fetch_tenders_page(self) -> bool:
        """Navigate to the tenders page."""
        try:
            print(f"Loading {self.BASE_URL}...")
            self.driver.get(self.BASE_URL)
            time.sleep(3)
            
            # Wait for content to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
            except TimeoutException:
                pass
            
            return True
        except Exception as e:
            print(f"Error loading page: {e}")
            return False
    
    def parse_tenders(self) -> List[Tender]:
        """Parse tender listings from the loaded page."""
        tenders = []
        
        # Get page source for debugging
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        
        # Check if we're still on login page
        if "Log in to your account" in page_text or "forgotten my password" in page_text.lower():
            print("WARNING: Still on login page. Authentication required.")
            return []
        
        # Try multiple parsing strategies
        
        # Strategy 1: Parse tables
        tables = self.driver.find_elements(By.TAG_NAME, "table")
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            if len(rows) > 1:
                header_row = rows[0]
                headers = [th.text.strip().lower() for th in header_row.find_elements(By.TAG_NAME, "th")]
                if not headers:
                    headers = [td.text.strip().lower() for td in header_row.find_elements(By.TAG_NAME, "td")]
                
                header_map = self._get_header_mapping(headers)
                
                for row in rows[1:]:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells:
                        tender = self._parse_table_row(cells, header_map, row)
                        if tender and tender.title:
                            tenders.append(tender)
        
        # Strategy 2: Look for grid/card items
        if not tenders:
            tenders = self._parse_grid_items()
        
        # Strategy 3: Look for any tender-related links
        if not tenders:
            tenders = self._parse_tender_links()
        
        return tenders
    
    def _get_header_mapping(self, headers: List[str]) -> dict:
        """Create a mapping of field names to column indices."""
        mapping = {}
        for i, header in enumerate(headers):
            if any(kw in header for kw in ['title', 'name', 'tender', 'description', 'opportunity']):
                mapping['title'] = i
            elif any(kw in header for kw in ['ref', 'number', 'id', 'code']):
                mapping['reference'] = i
            elif any(kw in header for kw in ['deadline', 'closing', 'end', 'due']):
                mapping['deadline'] = i
            elif any(kw in header for kw in ['category', 'type', 'sector']):
                mapping['category'] = i
            elif any(kw in header for kw in ['status', 'state', 'stage']):
                mapping['status'] = i
        return mapping
    
    def _parse_table_row(self, cells, header_map: dict, row) -> Optional[Tender]:
        """Parse a table row into a Tender object."""
        cell_texts = [cell.text.strip() for cell in cells]
        
        if not any(cell_texts):
            return None
        
        url = None
        try:
            link = row.find_element(By.TAG_NAME, "a")
            url = link.get_attribute("href")
        except NoSuchElementException:
            pass
        
        title = None
        if 'title' in header_map and header_map['title'] < len(cell_texts):
            title = cell_texts[header_map['title']]
        
        if not title:
            try:
                link = row.find_element(By.TAG_NAME, "a")
                title = link.text.strip()
            except NoSuchElementException:
                for text in cell_texts:
                    if text and len(text) > 3:
                        title = text
                        break
        
        if not title or title.lower() in ['', 'title', 'name', 'description']:
            return None
        
        return Tender(
            title=title,
            reference=cell_texts[header_map['reference']] if 'reference' in header_map and header_map['reference'] < len(cell_texts) else None,
            deadline=cell_texts[header_map['deadline']] if 'deadline' in header_map and header_map['deadline'] < len(cell_texts) else None,
            category=cell_texts[header_map['category']] if 'category' in header_map and header_map['category'] < len(cell_texts) else None,
            status=cell_texts[header_map['status']] if 'status' in header_map and header_map['status'] < len(cell_texts) else None,
            url=url
        )
    
    def _parse_grid_items(self) -> List[Tender]:
        """Parse grid/card-based layouts."""
        tenders = []
        
        selectors = [
            "div.tender-item", "div.tender-card", "div.opportunity",
            "div.listing-item", "div.result-item", "article.tender",
            "div[class*='tender']", "div[class*='item']"
        ]
        
        for selector in selectors:
            try:
                items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for item in items:
                    title = None
                    url = None
                    
                    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'a', 'strong']:
                        try:
                            elem = item.find_element(By.TAG_NAME, tag)
                            title = elem.text.strip()
                            if title:
                                break
                        except NoSuchElementException:
                            continue
                    
                    try:
                        link = item.find_element(By.TAG_NAME, "a")
                        url = link.get_attribute("href")
                        if not title:
                            title = link.text.strip()
                    except NoSuchElementException:
                        pass
                    
                    if title and len(title) > 3:
                        tenders.append(Tender(title=title, url=url))
                
                if tenders:
                    break
            except Exception:
                continue
        
        return tenders
    
    def _parse_tender_links(self) -> List[Tender]:
        """Parse tender-related links from the page."""
        tenders = []
        seen = set()
        
        links = self.driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                
                if not text or len(text) < 5:
                    continue
                
                if text.lower() in ['home', 'login', 'register', 'contact', 'help', 'back', 'next', 'previous', 'search']:
                    continue
                
                if any(kw in href.lower() for kw in ['tender', 'opportunity', 'notice', 'contract', 'procurement']):
                    if text not in seen:
                        seen.add(text)
                        tenders.append(Tender(title=text, url=href))
            except Exception:
                continue
        
        return tenders
    
    def scrape(self) -> List[Tender]:
        """Main scraping method."""
        try:
            self._setup_driver()
            
            # Try to login if credentials are provided
            if self.email and self.password:
                if not self.login():
                    print("Login failed. Trying to access public tenders...")
            
            if not self.fetch_tenders_page():
                return []
            
            tenders = self.parse_tenders()
            print(f"Found {len(tenders)} tenders.")
            
            return tenders
        finally:
            self._close_driver()
    
    def save_to_csv(self, tenders: List[Tender], filename: str = None) -> str:
        """Save tenders to a CSV file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gggi_tenders_{timestamp}.csv"
        
        fieldnames = [f.name for f in fields(Tender)]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for tender in tenders:
                row = {
                    'title': tender.title,
                    'reference': tender.reference or '',
                    'deadline': tender.deadline or '',
                    'category': tender.category or '',
                    'status': tender.status or '',
                    'description': tender.description or '',
                    'url': tender.url or ''
                }
                writer.writerow(row)
        
        print(f"Saved {len(tenders)} tenders to {filename}")
        return filename


def main():
    """Main entry point."""
    print("="*60)
    print("GGGI Tender Scraper")
    print("="*60)
    print("\nNOTE: This website requires login credentials.")
    print("Set environment variables GGGI_EMAIL and GGGI_PASSWORD")
    print("to access the tender listings.\n")
    
    # Check for credentials
    email = os.environ.get('GGGI_EMAIL')
    password = os.environ.get('GGGI_PASSWORD')
    
    if not email or not password:
        print("WARNING: No credentials provided.")
        print("The scraper will attempt to access public content only.\n")
    
    scraper = GGGITenderScraper(email=email, password=password, headless=True)
    tenders = scraper.scrape()
    
    if tenders:
        print("\nTenders Found:")
        print("-"*60)
        
        for i, tender in enumerate(tenders, 1):
            print(f"\n{i}. {tender.title}")
            if tender.reference:
                print(f"   Reference: {tender.reference}")
            if tender.deadline:
                print(f"   Deadline: {tender.deadline}")
            if tender.category:
                print(f"   Category: {tender.category}")
            if tender.status:
                print(f"   Status: {tender.status}")
            if tender.url:
                print(f"   URL: {tender.url}")
        
        csv_file = scraper.save_to_csv(tenders)
        print(f"\n{'='*60}")
        print(f"Results saved to: {csv_file}")
    else:
        print("\nNo tenders found.")
        print("\nThis website requires authentication to view tenders.")
        print("Please provide login credentials:")
        print("  export GGGI_EMAIL='your-email@example.com'")
        print("  export GGGI_PASSWORD='your-password'")
        print("\nThen run the scraper again.")


if __name__ == "__main__":
    main()
