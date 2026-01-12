#!/usr/bin/env python3
"""
WWF Pakistan Consultancy Scraper
Extracts consultancy/job opportunities from WWF Pakistan website
URL: https://wwf.org.pk/consultancy/
"""

import csv
import json
import re
from datetime import datetime
from typing import Optional, List, Dict
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup


class WWFConsultancyScraper:
    """Scraper for WWF Pakistan consultancy opportunities."""
    
    BASE_URL = "https://wwf.org.pk"
    CONSULTANCY_URL = "https://wwf.org.pk/consultancy/"
    APPLICATION_FORM = "https://forms.office.com/e/sxNStCNxPM"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.consultancies = []
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page and return BeautifulSoup object."""
        try:
            response = self.session.get(url, timeout=30)
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
    
    def extract_title_from_filename(self, filename: str) -> str:
        """Extract a clean title from PDF filename."""
        # Remove file extension
        title = re.sub(r'\.pdf$', '', filename, flags=re.I)
        
        # Remove leading numbers and dashes (e.g., "653-16318-")
        title = re.sub(r'^\d+-\d+-', '', title)
        title = re.sub(r'^\d+-', '', title)
        
        # Replace underscores and hyphens with spaces
        title = title.replace('_', ' ').replace('-', ' ')
        
        # Remove multiple spaces
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Clean up common patterns
        title = re.sub(r'\s*\(\d+\)\s*$', '', title)  # Remove trailing (1), (2), etc.
        title = re.sub(r'\s*v\d+\.?\d*\s*$', '', title, flags=re.I)  # Remove version numbers
        title = re.sub(r'\s*Final\s*$', '', title, flags=re.I)
        title = re.sub(r'\s*compressed\s*$', '', title, flags=re.I)
        title = re.sub(r'\s*Copy\s*$', '', title, flags=re.I)
        
        return title.strip()
    
    def extract_reference_number(self, filename: str) -> str:
        """Extract reference number from filename."""
        # Look for patterns like "653-16318-" at the start
        match = re.search(r'^(\d+)', filename)
        if match:
            return match.group(1)
        return ""
    
    def extract_consultancies(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract consultancy information from the page."""
        consultancies = []
        seen_pdfs = set()
        
        # Find all PDF links (Terms of References)
        for link in soup.find_all("a", href=re.compile(r"\.pdf$", re.I)):
            href = link.get("href", "")
            
            # Skip if we've already processed this PDF
            if href in seen_pdfs:
                continue
            seen_pdfs.add(href)
            
            # Extract filename from URL
            filename = unquote(href.split("/")[-1])
            
            # Extract title from filename
            title = self.extract_title_from_filename(filename)
            
            if not title or len(title) < 5:
                continue
            
            # Create consultancy entry
            consultancy = {
                "title": title,
                "reference_number": self.extract_reference_number(filename),
                "tor_document": href,
                "application_form": self.APPLICATION_FORM,
                "source_page": self.CONSULTANCY_URL,
            }
            
            # Try to extract category/type from title
            title_lower = title.lower()
            if "audit" in title_lower:
                consultancy["category"] = "Audit"
            elif "training" in title_lower:
                consultancy["category"] = "Training"
            elif "assessment" in title_lower or "study" in title_lower:
                consultancy["category"] = "Assessment/Study"
            elif "gis" in title_lower or "mapping" in title_lower:
                consultancy["category"] = "GIS/Mapping"
            elif "consultant" in title_lower or "consultancy" in title_lower:
                consultancy["category"] = "Consultancy"
            elif "tors" in title_lower or "tor" in title_lower:
                consultancy["category"] = "Consultancy"
            else:
                consultancy["category"] = "General"
            
            # Try to extract location from title
            pakistan_locations = [
                "Karachi", "Lahore", "Islamabad", "Peshawar", "Quetta",
                "Chitral", "Gilgit", "GB", "KP", "Punjab", "Sindh", 
                "Balochistan", "AJK", "FATA", "RYK"
            ]
            for loc in pakistan_locations:
                if loc.lower() in title_lower:
                    consultancy["location"] = loc
                    break
            
            consultancies.append(consultancy)
        
        return consultancies
    
    def scrape_all_consultancies(self) -> List[Dict]:
        """Scrape all consultancies from the website."""
        print(f"Starting to scrape consultancies from: {self.CONSULTANCY_URL}")
        
        soup = self.fetch_page(self.CONSULTANCY_URL)
        if not soup:
            print("Failed to fetch the page.")
            return []
        
        self.consultancies = self.extract_consultancies(soup)
        
        # Sort by reference number (newest first)
        self.consultancies.sort(
            key=lambda x: int(x.get("reference_number") or "0"),
            reverse=True
        )
        
        print(f"Total consultancies found: {len(self.consultancies)}")
        return self.consultancies
    
    def save_to_csv(self, filename: str = "wwf_consultancies.csv") -> str:
        """Save consultancies to CSV file."""
        if not self.consultancies:
            print("No consultancies to save.")
            return ""
        
        columns = [
            "reference_number", "title", "category", "location",
            "tor_document", "application_form", "source_page"
        ]
        
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.consultancies)
        
        print(f"Saved {len(self.consultancies)} consultancies to {filename}")
        return filename
    
    def save_to_json(self, filename: str = "wwf_consultancies.json") -> str:
        """Save consultancies to JSON file."""
        if not self.consultancies:
            print("No consultancies to save.")
            return ""
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.consultancies, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(self.consultancies)} consultancies to {filename}")
        return filename


def main():
    """Main function to run the scraper."""
    print("=" * 60)
    print("WWF Pakistan Consultancy Scraper")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    scraper = WWFConsultancyScraper()
    items = scraper.scrape_all_consultancies()
    
    if items:
        csv_file = scraper.save_to_csv("wwf_consultancies.csv")
        json_file = scraper.save_to_json("wwf_consultancies.json")
        
        print()
        print("=" * 60)
        print("Scraping completed!")
        print(f"Total consultancies extracted: {len(items)}")
        print(f"CSV file: {csv_file}")
        print(f"JSON file: {json_file}")
        print("=" * 60)
        
        print("\nSample data (latest 5):")
        for item in items[:5]:
            print(f"  [{item.get('reference_number', 'N/A')}] {item.get('title', 'N/A')[:55]}...")
            print(f"       Category: {item.get('category', 'N/A')}, Location: {item.get('location', 'N/A')}")
    else:
        print("\nNo consultancies were found.")
    
    return items


if __name__ == "__main__":
    main()
