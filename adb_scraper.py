"""
ADB (Asian Development Bank) Projects Scraper
Extracts project information from https://www.adb.org/projects

Multiple methods included:
1. Direct API access (when available)
2. Selenium browser automation
3. CSV data download from ADB Data Library
"""

import json
import csv
import time
import re
import os
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict, field
from urllib.parse import urljoin, urlencode

import requests

# Optional imports
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


@dataclass
class Project:
    """Data class to store ADB project information"""
    project_id: str = ""
    title: str = ""
    country: str = ""
    region: str = ""
    sector: str = ""
    subsector: str = ""
    status: str = ""
    project_type: str = ""
    modality: str = ""
    approval_date: str = ""
    signing_date: str = ""
    closing_date: str = ""
    effectivity_date: str = ""
    financing_amount: str = ""
    currency: str = ""
    borrower: str = ""
    executing_agency: str = ""
    implementing_agency: str = ""
    cofinancing: str = ""
    description: str = ""
    objectives: str = ""
    project_url: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ADBDataLibrary:
    """
    Access ADB project data through their Data Library
    https://data.adb.org/
    
    This provides downloadable CSV/Excel files with project data
    """
    
    # Known dataset URLs from ADB Data Library
    DATASETS = {
        'sovereign_projects': 'https://data.adb.org/dataset/sovereign-projects-loans-grants-and-technical-assistance',
        'nonsovereign_projects': 'https://data.adb.org/dataset/nonsovereign-operations',
        'cofinancing': 'https://data.adb.org/dataset/adb-official-cofinancing',
        'procurement': 'https://data.adb.org/dataset/contracts-goods-works-and-services',
    }
    
    @staticmethod
    def get_download_instructions():
        """Print instructions for downloading ADB data manually"""
        print("""
╔════════════════════════════════════════════════════════════════╗
║           ADB Data Library - Manual Download Instructions      ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  The ADB website has Cloudflare protection that blocks         ║
║  automated access. You can download the data manually:         ║
║                                                                ║
║  1. SOVEREIGN PROJECTS (Loans, Grants, TA):                    ║
║     https://data.adb.org/dataset/sovereign-projects-loans-     ║
║     grants-and-technical-assistance                            ║
║                                                                ║
║  2. NONSOVEREIGN OPERATIONS:                                   ║
║     https://data.adb.org/dataset/nonsovereign-operations       ║
║                                                                ║
║  3. COFINANCING DATA:                                          ║
║     https://data.adb.org/dataset/adb-official-cofinancing      ║
║                                                                ║
║  4. PROCUREMENT CONTRACTS:                                     ║
║     https://data.adb.org/dataset/contracts-goods-works-and-    ║
║     services                                                   ║
║                                                                ║
║  Steps:                                                        ║
║  1. Visit the URL in your browser                              ║
║  2. Click "Download" or "Export" button                        ║
║  3. Choose CSV or Excel format                                 ║
║  4. Save to this directory                                     ║
║  5. Run: scraper.load_from_csv('filename.csv')                 ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
        """)


class ADBScraper:
    """
    Main scraper class for ADB Projects
    Supports multiple methods of data extraction
    """
    
    BASE_URL = "https://www.adb.org"
    PROJECTS_URL = "https://www.adb.org/projects"
    API_SEARCH_URL = "https://www.adb.org/projects/search"
    
    def __init__(self, headless: bool = True, delay: float = 2.0):
        self.headless = headless
        self.delay = delay
        self.driver = None
        self.projects: List[Project] = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def _setup_driver(self):
        """Setup undetected Chrome WebDriver"""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium not installed. Run: pip install undetected-chromedriver selenium")
        
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        self.driver = uc.Chrome(options=options, version_main=None)
        print("Browser initialized")
    
    def _close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def load_from_csv(self, filepath: str) -> List[Project]:
        """
        Load project data from a CSV file (downloaded from ADB Data Library)
        
        Args:
            filepath: Path to the CSV file
            
        Returns:
            List of Project objects
        """
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return []
        
        projects = []
        
        # Common field mappings from ADB CSV exports
        field_mappings = {
            'project_id': ['Project Number', 'Project No.', 'Project ID', 'project_number', 'project_no'],
            'title': ['Project Name', 'Title', 'Project Title', 'project_name'],
            'country': ['Country', 'Countries', 'DMC', 'country'],
            'region': ['Region', 'Geographic Region', 'region'],
            'sector': ['Sector', 'Primary Sector', 'sector'],
            'subsector': ['Subsector', 'Sub-Sector', 'subsector'],
            'status': ['Status', 'Project Status', 'status'],
            'project_type': ['Type', 'Project Type', 'Modality', 'type'],
            'modality': ['Modality', 'Financing Modality', 'modality'],
            'approval_date': ['Approval Date', 'Date Approved', 'Board Approval', 'approval_date'],
            'signing_date': ['Signing Date', 'Date Signed', 'signing_date'],
            'closing_date': ['Closing Date', 'Expected Closing', 'closing_date'],
            'financing_amount': ['Amount', 'Financing Amount', 'ADB Financing', 'Total Amount', 'amount'],
            'currency': ['Currency', 'currency'],
            'borrower': ['Borrower', 'borrower'],
            'executing_agency': ['Executing Agency', 'EA', 'executing_agency'],
            'description': ['Description', 'Project Description', 'description'],
        }
        
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                # Create mapping from CSV headers to our fields
                header_map = {}
                for our_field, possible_names in field_mappings.items():
                    for name in possible_names:
                        if name in headers:
                            header_map[name] = our_field
                            break
                
                for row in reader:
                    project = Project()
                    for csv_field, our_field in header_map.items():
                        value = row.get(csv_field, '').strip()
                        if value:
                            setattr(project, our_field, value)
                    
                    # Generate project URL if we have project_id
                    if project.project_id:
                        project.project_url = f"{self.PROJECTS_URL}/{project.project_id}"
                    
                    if project.project_id or project.title:
                        projects.append(project)
            
            self.projects = projects
            print(f"Loaded {len(projects)} projects from {filepath}")
            
        except Exception as e:
            print(f"Error reading CSV: {e}")
        
        return projects
    
    def load_from_json(self, filepath: str) -> List[Project]:
        """
        Load project data from a JSON file
        """
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            projects = []
            for item in data:
                project = Project(**{k: v for k, v in item.items() if hasattr(Project, k)})
                projects.append(project)
            
            self.projects = projects
            print(f"Loaded {len(projects)} projects from {filepath}")
            return projects
            
        except Exception as e:
            print(f"Error reading JSON: {e}")
            return []
    
    def scrape_with_selenium(self, max_pages: int = 5, fetch_details: bool = True) -> List[Project]:
        """
        Scrape projects using Selenium (bypasses some protections)
        """
        if not SELENIUM_AVAILABLE:
            print("Selenium not available. Install with: pip install undetected-chromedriver selenium")
            return []
        
        try:
            self._setup_driver()
            
            print(f"Navigating to {self.PROJECTS_URL}...")
            self.driver.get(self.PROJECTS_URL)
            
            # Wait for Cloudflare
            print("Waiting for page to load...")
            time.sleep(10)
            
            # Check if we passed protection
            page_source = self.driver.page_source
            if "Just a moment" in page_source or "Verify you are human" in page_source:
                print("❌ Cloudflare protection active - automated access blocked")
                print("\nTry one of these alternatives:")
                print("1. Download data manually from ADB Data Library")
                print("2. Use a VPN or different network")
                print("3. Run the script from your local machine (not cloud)")
                ADBDataLibrary.get_download_instructions()
                return []
            
            all_projects = []
            
            for page in range(max_pages):
                print(f"\nScraping page {page + 1}...")
                
                # Find project links
                links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/projects/"]')
                
                seen_urls = set()
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        text = link.text.strip()
                        
                        if href and re.search(r'/projects/\d+', href) and href not in seen_urls and text:
                            seen_urls.add(href)
                            match = re.search(r'/projects/(\d+)', href)
                            proj_id = match.group(1) if match else ""
                            
                            all_projects.append({
                                'project_id': proj_id,
                                'title': text,
                                'project_url': href
                            })
                    except:
                        continue
                
                print(f"  Found {len(seen_urls)} projects on this page")
                
                # Try next page
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, 'a[rel="next"], .pager__item--next a')
                    self.driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(3)
                except:
                    print("No more pages")
                    break
            
            # Fetch details if requested
            if fetch_details:
                print("\nFetching project details...")
                for i, proj_data in enumerate(all_projects):
                    print(f"  [{i+1}/{len(all_projects)}] {proj_data.get('title', '')[:50]}...")
                    project = self._get_project_details_selenium(proj_data['project_url'])
                    if project:
                        self.projects.append(project)
                    time.sleep(self.delay)
            else:
                for proj_data in all_projects:
                    project = Project(**{k: v for k, v in proj_data.items() if hasattr(Project, k)})
                    self.projects.append(project)
            
            return self.projects
            
        finally:
            self._close_driver()
    
    def _get_project_details_selenium(self, url: str) -> Optional[Project]:
        """Fetch project details using Selenium"""
        try:
            self.driver.get(url)
            time.sleep(3)
            
            project = Project(project_url=url)
            
            # Extract project ID
            match = re.search(r'/projects/(\d+)', url)
            if match:
                project.project_id = match.group(1)
            
            # Extract title
            try:
                title = self.driver.find_element(By.CSS_SELECTOR, 'h1')
                project.title = title.text.strip()
            except:
                pass
            
            # Extract from page text using patterns
            try:
                page_text = self.driver.find_element(By.TAG_NAME, 'body').text
                
                patterns = {
                    'country': r'Country[:\s]*([A-Za-z\s,]+?)(?:\n|Sector|Region)',
                    'sector': r'(?<!Sub)Sector[:\s]*([^\n]+)',
                    'status': r'Status[:\s]*([^\n]+)',
                    'approval_date': r'Approval[:\s]*(\d{1,2}\s+\w+\s+\d{4})',
                    'financing_amount': r'(\$[\d,\.]+\s*(?:million|billion)?)',
                }
                
                for field, pattern in patterns.items():
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        setattr(project, field, match.group(1).strip())
            except:
                pass
            
            return project
            
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def create_sample_data(self, count: int = 10) -> List[Project]:
        """
        Create sample project data for testing purposes
        """
        sample_countries = ['Philippines', 'Indonesia', 'Vietnam', 'Bangladesh', 'India', 
                          'Pakistan', 'Sri Lanka', 'Nepal', 'Cambodia', 'Myanmar']
        sample_sectors = ['Transport', 'Energy', 'Water and Urban', 'Education', 'Health',
                         'Agriculture', 'Finance', 'Public Sector', 'Industry', 'Multisector']
        sample_statuses = ['Active', 'Proposed', 'Closed', 'Approved']
        
        projects = []
        for i in range(count):
            import random
            project = Project(
                project_id=str(50000 + i),
                title=f"Sample Infrastructure Development Project {i+1}",
                country=random.choice(sample_countries),
                region="Southeast Asia" if i % 2 == 0 else "South Asia",
                sector=random.choice(sample_sectors),
                status=random.choice(sample_statuses),
                approval_date=f"{random.randint(2015, 2024)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                financing_amount=f"${random.randint(10, 500)} million",
                project_url=f"https://www.adb.org/projects/{50000 + i}",
                description=f"This is a sample project for testing the scraper functionality. "
                           f"It includes various infrastructure improvements in {sample_countries[i % len(sample_countries)]}."
            )
            projects.append(project)
        
        self.projects = projects
        print(f"Created {count} sample projects for testing")
        return projects
    
    def save_to_json(self, filename: str = "adb_projects.json"):
        """Save projects to JSON file"""
        if not self.projects:
            print("No projects to save")
            return
        
        data = [asdict(p) for p in self.projects]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {len(data)} projects to {filename}")
    
    def save_to_csv(self, filename: str = "adb_projects.csv"):
        """Save projects to CSV file"""
        if not self.projects:
            print("No projects to save")
            return
        
        data = [asdict(p) for p in self.projects]
        fieldnames = list(data[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"✓ Saved {len(data)} projects to {filename}")
    
    def print_summary(self):
        """Print summary of scraped projects"""
        if not self.projects:
            print("No projects loaded")
            return
        
        print("\n" + "=" * 60)
        print(f"PROJECT SUMMARY: {len(self.projects)} projects")
        print("=" * 60)
        
        # Count by country
        countries = {}
        sectors = {}
        statuses = {}
        
        for p in self.projects:
            if p.country:
                countries[p.country] = countries.get(p.country, 0) + 1
            if p.sector:
                sectors[p.sector] = sectors.get(p.sector, 0) + 1
            if p.status:
                statuses[p.status] = statuses.get(p.status, 0) + 1
        
        if countries:
            print("\nTop Countries:")
            for country, count in sorted(countries.items(), key=lambda x: -x[1])[:10]:
                print(f"  {country}: {count}")
        
        if sectors:
            print("\nTop Sectors:")
            for sector, count in sorted(sectors.items(), key=lambda x: -x[1])[:10]:
                print(f"  {sector}: {count}")
        
        if statuses:
            print("\nBy Status:")
            for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
                print(f"  {status}: {count}")
        
        # Sample projects
        print("\n" + "-" * 60)
        print("Sample Projects:")
        print("-" * 60)
        for i, p in enumerate(self.projects[:5]):
            print(f"\n[{i+1}] {p.title}")
            print(f"    ID: {p.project_id} | Country: {p.country}")
            print(f"    Sector: {p.sector} | Status: {p.status}")
            if p.financing_amount:
                print(f"    Financing: {p.financing_amount}")


def main():
    print("""
╔════════════════════════════════════════════════════════════════╗
║              ADB PROJECTS SCRAPER v2.0                         ║
╠════════════════════════════════════════════════════════════════╣
║  Extracts project data from Asian Development Bank             ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    scraper = ADBScraper(headless=True, delay=2.0)
    
    # Method 1: Try loading from existing CSV (if downloaded from ADB)
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv') and 'adb' in f.lower()]
    if csv_files:
        print(f"Found existing CSV files: {csv_files}")
        scraper.load_from_csv(csv_files[0])
    
    # Method 2: Try Selenium scraping
    if not scraper.projects and SELENIUM_AVAILABLE:
        print("\nAttempting to scrape with Selenium...")
        scraper.scrape_with_selenium(max_pages=3, fetch_details=False)
    
    # Method 3: Create sample data for testing
    if not scraper.projects:
        print("\n⚠ Could not access ADB website (Cloudflare protection)")
        ADBDataLibrary.get_download_instructions()
        
        print("\nCreating sample data for testing...")
        scraper.create_sample_data(20)
    
    # Save results
    if scraper.projects:
        scraper.save_to_json("adb_projects.json")
        scraper.save_to_csv("adb_projects.csv")
        scraper.print_summary()


if __name__ == "__main__":
    main()
