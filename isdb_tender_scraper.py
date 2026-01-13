#!/usr/bin/env python3
"""
IsDB Tender Scraper
Extracts tender/project procurement information from the Islamic Development Bank website
URL: https://www.isdb.org/project-procurement/tenders
"""

import csv
import json
import time
import re
from datetime import datetime
from typing import Optional, List, Dict
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup


class IsDBTenderScraper:
    """Scraper for IsDB project procurement tenders."""
    
    BASE_URL = "https://www.isdb.org"
    TENDERS_URL = "https://www.isdb.org/project-procurement/tenders"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }
    
    # Mapping URL patterns to tender types
    TENDER_TYPE_MAP = {
        "/eoi/": "Expression of Interest",
        "/gpn/": "General Procurement Notice",
        "/spn/": "Specific Procurement Notice",
        "/pqn/": "Pre-Qualification Notice",
        "/contract-award/": "Contract Award",
        "/rfp/": "Request for Proposal",
        "/itb/": "Invitation to Bid",
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.tenders = []
    
    def fetch_page(self, url: str, params: Optional[dict] = None) -> Optional[BeautifulSoup]:
        """Fetch a page and return BeautifulSoup object."""
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def clean_text(self, text: str) -> str:
        """Clean extracted text."""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def extract_tender_type_from_url(self, url: str) -> str:
        """Extract tender type from URL pattern."""
        if not url:
            return ""
        url_lower = url.lower()
        for pattern, tender_type in self.TENDER_TYPE_MAP.items():
            if pattern in url_lower:
                return tender_type
        return ""
    
    def extract_tenders_from_page(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract tender information from a page."""
        tenders = []
        
        # Look for views-row items (Drupal structure)
        tender_rows = soup.find_all("div", class_=re.compile(r"views-row"))
        
        for row in tender_rows:
            tender = self._extract_tender_from_row(row)
            if tender and tender.get("title"):
                tenders.append(tender)
        
        # If no views-row, try table structure
        if not tenders:
            tables = soup.find_all("table")
            for table in tables:
                tenders.extend(self._extract_from_table(table))
        
        # Look for article/card items
        if not tenders:
            articles = soup.find_all(["article", "div"], class_=re.compile(r"tender|procurement|node", re.I))
            for article in articles:
                tender = self._extract_tender_from_row(article)
                if tender and tender.get("title"):
                    tenders.append(tender)
        
        return tenders
    
    def _extract_tender_from_row(self, row) -> Dict:
        """Extract tender data from a row element."""
        tender = {}
        
        # Extract title and link
        title_elem = (
            row.find("h2") or 
            row.find("h3") or 
            row.find("h4") or
            row.find(class_=re.compile(r"title|heading", re.I)) or
            row.find("strong")
        )
        
        if title_elem:
            link = title_elem.find("a") if title_elem.name != "a" else title_elem
            if not link:
                link = title_elem.parent if title_elem.parent and title_elem.parent.name == "a" else None
            
            if link and link.name == "a":
                tender["title"] = self.clean_text(link.get_text())
                href = link.get("href", "")
                if href:
                    full_url = urljoin(self.BASE_URL, href)
                    tender["link"] = full_url
                    # Extract tender type from URL
                    tender["tender_type"] = self.extract_tender_type_from_url(full_url)
            else:
                tender["title"] = self.clean_text(title_elem.get_text())
        
        # Look for field items
        fields = row.find_all("div", class_=re.compile(r"field--name|field-content|views-field"))
        
        for field in fields:
            field_class = " ".join(field.get("class", []))
            text = self.clean_text(field.get_text())
            
            if not text or text == tender.get("title"):
                continue
            
            # Determine field type
            if "status" in field_class.lower():
                tender["status"] = text
            elif "country" in field_class.lower() or "location" in field_class.lower():
                tender["country"] = text
            elif "type" in field_class.lower() or "category" in field_class.lower():
                # Check if it's actually a date
                if re.match(r'\d{1,2}\s+\w+\s+\d{4}', text):
                    tender["deadline"] = text
                else:
                    tender["tender_type"] = text
            elif "date" in field_class.lower() or "deadline" in field_class.lower():
                tender["deadline"] = text
            elif "reference" in field_class.lower() or "number" in field_class.lower():
                tender["reference"] = text
        
        # Parse remaining text for missed fields
        if len(tender) <= 2:
            tender = self._parse_tender_text(row, tender)
        
        return tender
    
    def _parse_tender_text(self, row, tender: Dict) -> Dict:
        """Parse tender info from text content."""
        text_blocks = []
        for elem in row.find_all(["span", "div", "p"], recursive=True):
            text = self.clean_text(elem.get_text())
            if text and len(text) < 100 and text not in text_blocks:
                text_blocks.append(text)
        
        status_keywords = ["open", "closed", "fermé", "ouvert", "active", "expired"]
        type_keywords = ["expression of interest", "general procurement notice", 
                        "specific procurement notice", "pre-qualification", 
                        "contract award", "request for proposal", "eoi", "gpn", "spn"]
        
        for text in text_blocks:
            text_lower = text.lower()
            
            # Check for status
            if not tender.get("status"):
                for status in status_keywords:
                    if status in text_lower and len(text) < 20:
                        tender["status"] = text
                        break
            
            # Check for tender type (but not dates)
            if not tender.get("tender_type") and not re.match(r'\d{1,2}\s+\w+\s+\d{4}', text):
                for ttype in type_keywords:
                    if ttype in text_lower:
                        tender["tender_type"] = text
                        break
            
            # Check for date
            if not tender.get("deadline"):
                date_match = re.search(r'\d{1,2}\s+\w+\s+\d{4}', text)
                if date_match:
                    tender["deadline"] = date_match.group()
            
            # Check for country
            if not tender.get("country"):
                country_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)$', text)
                if country_match and len(text) < 30:
                    potential_country = country_match.group(1)
                    if potential_country.lower() not in ["open", "closed", "active"]:
                        tender["country"] = potential_country
        
        return tender
    
    def _extract_from_table(self, table) -> List[Dict]:
        """Extract tenders from a table structure."""
        tenders = []
        rows = table.find_all("tr")
        headers = []
        
        for row in rows:
            header_cells = row.find_all("th")
            if header_cells:
                headers = [self.clean_text(th.get_text()).lower() for th in header_cells]
                continue
            
            cells = row.find_all("td")
            if not cells:
                continue
            
            tender = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    key = headers[i]
                else:
                    key = f"column_{i}"
                
                link = cell.find("a")
                if link:
                    tender[key] = self.clean_text(link.get_text())
                    href = link.get("href", "")
                    if href:
                        full_url = urljoin(self.BASE_URL, href)
                        tender[f"{key}_link"] = full_url
                        if key == "title":
                            tender["tender_type"] = self.extract_tender_type_from_url(full_url)
                else:
                    tender[key] = self.clean_text(cell.get_text())
            
            if tender:
                tenders.append(tender)
        
        return tenders
    
    def get_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Find the next page URL."""
        pager = soup.find(["nav", "ul", "div"], class_=re.compile(r"pager|pagination"))
        if pager:
            next_link = pager.find("a", class_=re.compile(r"next", re.I))
            if not next_link:
                next_link = pager.find("a", string=re.compile(r"next|›|»", re.I))
            if not next_link:
                next_link = pager.find("a", rel="next")
            
            if next_link and next_link.get("href"):
                return urljoin(self.BASE_URL, next_link.get("href"))
        
        return None
    
    def scrape_all_tenders(self, max_pages: int = 100) -> List[Dict]:
        """Scrape all tenders from all pages."""
        print(f"Starting to scrape tenders from: {self.TENDERS_URL}")
        
        current_url = self.TENDERS_URL
        page_count = 0
        visited_urls = set()
        
        while current_url and page_count < max_pages:
            if current_url in visited_urls:
                break
            
            visited_urls.add(current_url)
            page_count += 1
            
            print(f"Scraping page {page_count}: {current_url}")
            
            soup = self.fetch_page(current_url)
            if not soup:
                break
            
            page_tenders = self.extract_tenders_from_page(soup)
            print(f"  Found {len(page_tenders)} tenders on this page")
            
            self.tenders.extend(page_tenders)
            
            # Get next page
            next_url = self.get_next_page_url(soup, current_url)
            if next_url and next_url != current_url:
                current_url = next_url
            else:
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                current_page = int(params.get("page", [0])[0])
                next_url = f"{self.TENDERS_URL}?page={current_page + 1}"
                if next_url not in visited_urls:
                    test_soup = self.fetch_page(next_url)
                    if test_soup and self.extract_tenders_from_page(test_soup):
                        current_url = next_url
                    else:
                        current_url = None
                else:
                    current_url = None
            
            time.sleep(1)
        
        # Clean and deduplicate
        self.tenders = self._remove_duplicates(self.tenders)
        self.tenders = self._clean_data(self.tenders)
        
        print(f"\nTotal unique tenders found: {len(self.tenders)}")
        return self.tenders
    
    def _remove_duplicates(self, tenders: List[Dict]) -> List[Dict]:
        """Remove duplicate tenders."""
        seen = set()
        unique = []
        
        for tender in tenders:
            key = tender.get("link") or tender.get("title", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(tender)
        
        return unique
    
    def _clean_data(self, tenders: List[Dict]) -> List[Dict]:
        """Clean up tender data."""
        cleaned = []
        
        for tender in tenders:
            if not tender.get("title") or len(tender.get("title", "")) < 5:
                continue
            
            # Fix misplaced deadline in tender_type
            if tender.get("tender_type"):
                if re.match(r'\d{1,2}\s+\w+\s+\d{4}', tender["tender_type"]):
                    if not tender.get("deadline"):
                        tender["deadline"] = tender["tender_type"]
                    # Try to get type from URL
                    if tender.get("link"):
                        tender["tender_type"] = self.extract_tender_type_from_url(tender["link"])
                    else:
                        del tender["tender_type"]
            
            # Clean status
            if tender.get("status"):
                status = tender["status"].lower()
                if "closed" in status or "fermé" in status:
                    tender["status"] = "Closed"
                elif "open" in status or "ouvert" in status:
                    tender["status"] = "Open"
            
            # Clean reference if it's just status
            if tender.get("reference") in ["Closed", "Fermé", "Open", "Ouvert"]:
                if not tender.get("status"):
                    tender["status"] = tender["reference"]
                del tender["reference"]
            
            # Truncate very long fields
            for key in list(tender.keys()):
                value = tender[key]
                if isinstance(value, str) and len(value) > 300:
                    tender[key] = value[:297] + "..."
            
            cleaned.append(tender)
        
        return cleaned
    
    def save_to_csv(self, filename: str = "isdb_tenders.csv") -> str:
        """Save tenders to CSV file."""
        if not self.tenders:
            print("No tenders to save.")
            return ""
        
        all_keys = set()
        for tender in self.tenders:
            all_keys.update(tender.keys())
        
        preferred_order = [
            "title", "tender_type", "status", "country", "deadline",
            "reference", "description", "link", "documents"
        ]
        
        columns = [col for col in preferred_order if col in all_keys]
        columns.extend(sorted(all_keys - set(columns)))
        
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.tenders)
        
        print(f"Saved {len(self.tenders)} tenders to {filename}")
        return filename
    
    def save_to_json(self, filename: str = "isdb_tenders.json") -> str:
        """Save tenders to JSON file."""
        if not self.tenders:
            print("No tenders to save.")
            return ""
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.tenders, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(self.tenders)} tenders to {filename}")
        return filename


def main():
    """Main function to run the scraper."""
    print("=" * 60)
    print("IsDB Tender Scraper")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    scraper = IsDBTenderScraper()
    tenders = scraper.scrape_all_tenders(max_pages=100)
    
    if tenders:
        csv_file = scraper.save_to_csv("isdb_tenders.csv")
        json_file = scraper.save_to_json("isdb_tenders.json")
        
        print()
        print("=" * 60)
        print("Scraping completed!")
        print(f"Total tenders extracted: {len(tenders)}")
        print(f"CSV file: {csv_file}")
        print(f"JSON file: {json_file}")
        print("=" * 60)
        
        print("\nSample tender data:")
        for tender in tenders[:3]:
            print(f"  - {tender.get('title', 'N/A')[:60]}...")
            print(f"    Type: {tender.get('tender_type', 'N/A')}")
            print(f"    Country: {tender.get('country', 'N/A')}, Status: {tender.get('status', 'N/A')}")
            print(f"    Deadline: {tender.get('deadline', 'N/A')}")
    else:
        print("\nNo tenders were found.")
    
    return tenders


if __name__ == "__main__":
    main()
