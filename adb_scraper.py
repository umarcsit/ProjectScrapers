"""
ADB (Asian Development Bank) Projects Scraper
Extracts project information from https://www.adb.org/projects

Uses undetected-chromedriver to bypass Cloudflare protection.
"""

import json
import csv
import time
import re
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, asdict, field

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Required packages not installed. Run: pip install undetected-chromedriver selenium")


@dataclass
class Project:
    """Data class to store project information"""
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
    borrower: str = ""
    executing_agency: str = ""
    implementing_agency: str = ""
    description: str = ""
    objectives: str = ""
    project_url: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ADBScraper:
    """Scraper for Asian Development Bank projects using undetected-chromedriver"""
    
    BASE_URL = "https://www.adb.org"
    PROJECTS_URL = "https://www.adb.org/projects"
    
    def __init__(self, headless: bool = True, delay: float = 2.0):
        """
        Initialize the scraper
        
        Args:
            headless: Run browser in headless mode
            delay: Delay between actions in seconds
        """
        self.headless = headless
        self.delay = delay
        self.driver = None
        self.projects: List[Project] = []
    
    def _setup_driver(self):
        """Setup undetected Chrome WebDriver"""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Required packages not installed. Run: pip install undetected-chromedriver selenium")
        
        options = uc.ChromeOptions()
        
        if self.headless:
            options.add_argument('--headless=new')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        try:
            self.driver = uc.Chrome(options=options, version_main=None)
            print("Browser initialized successfully")
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            raise
    
    def _close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def _wait_for_page_load(self, timeout: int = 30):
        """Wait for page to fully load"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(self.delay)
        except TimeoutException:
            print("Page load timeout, continuing anyway...")
    
    def get_projects_from_listing(self, max_pages: int = 10) -> List[dict]:
        """
        Fetch projects from the ADB projects listing page
        """
        if not self.driver:
            self._setup_driver()
        
        all_projects = []
        
        print(f"Navigating to {self.PROJECTS_URL}...")
        self.driver.get(self.PROJECTS_URL)
        
        # Wait longer for Cloudflare challenge to complete
        print("Waiting for page to load (bypassing protection)...")
        time.sleep(8)
        self._wait_for_page_load()
        
        # Check if we passed Cloudflare
        if "Just a moment" in self.driver.page_source or "Verify you are human" in self.driver.page_source:
            print("Still on Cloudflare challenge page, waiting longer...")
            time.sleep(10)
        
        for page in range(max_pages):
            print(f"\nScraping page {page + 1}...")
            
            # Save page for debugging
            with open(f"debug_page_{page}.html", "w", encoding='utf-8') as f:
                f.write(self.driver.page_source)
            
            # Find all project links
            try:
                # Wait for content
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/projects/"]'))
                )
            except TimeoutException:
                print("Timeout waiting for project links")
            
            # Get all project links
            links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/projects/"]')
            print(f"  Found {len(links)} project links")
            
            seen_urls = set()
            for link in links:
                try:
                    href = link.get_attribute('href')
                    text = link.text.strip()
                    
                    # Filter for actual project pages (have numeric ID)
                    if href and re.search(r'/projects/\d+', href):
                        if href not in seen_urls and text:
                            seen_urls.add(href)
                            match = re.search(r'/projects/(\d+)', href)
                            proj_id = match.group(1) if match else ""
                            
                            all_projects.append({
                                'project_id': proj_id,
                                'title': text,
                                'project_url': href
                            })
                except Exception as e:
                    continue
            
            print(f"  Collected {len(all_projects)} unique projects so far")
            
            # Try to go to next page
            if not self._go_to_next_page():
                print("No more pages or pagination not found.")
                break
            
            time.sleep(self.delay)
        
        return all_projects
    
    def _go_to_next_page(self) -> bool:
        """Try to navigate to the next page"""
        try:
            next_selectors = [
                'a[rel="next"]',
                '.pager__item--next a',
                'a.pager__link--next',
                '.pager-next a',
                '.pagination .next a',
                'li.pager__item--next a',
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if next_btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", next_btn)
                        time.sleep(3)
                        self._wait_for_page_load()
                        return True
                except:
                    continue
            
            # Try by partial link text
            try:
                next_btn = self.driver.find_element(By.PARTIAL_LINK_TEXT, 'Next')
                self.driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(3)
                self._wait_for_page_load()
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            return False
    
    def get_project_details(self, project_url: str) -> Optional[Project]:
        """
        Fetch detailed information for a specific project
        """
        if not self.driver:
            self._setup_driver()
        
        try:
            self.driver.get(project_url)
            time.sleep(3)
            self._wait_for_page_load()
            
            # Check for Cloudflare
            if "Just a moment" in self.driver.page_source:
                time.sleep(8)
            
            project = Project(project_url=project_url)
            
            # Extract project ID from URL
            match = re.search(r'/projects/(\d+)', project_url)
            if match:
                project.project_id = match.group(1)
            
            # Extract title
            try:
                title = self.driver.find_element(By.CSS_SELECTOR, 'h1')
                project.title = title.text.strip()
            except:
                pass
            
            # Get page text for pattern matching
            try:
                page_text = self.driver.find_element(By.TAG_NAME, 'body').text
            except:
                page_text = ""
            
            # Extract fields using patterns
            field_patterns = {
                'project_id': [r'Project Number[:\s]*(\d+)', r'Project No\.[:\s]*(\d+)'],
                'country': [r'Country[:\s]*([A-Za-z,\s]+?)(?:\n|Sector|Region|$)'],
                'region': [r'Region[:\s]*([^\n]+)'],
                'sector': [r'(?<!Sub)Sector[:\s]*([^\n]+)'],
                'subsector': [r'Subsector[:\s]*([^\n]+)'],
                'status': [r'Status[:\s]*([^\n]+)'],
                'project_type': [r'Project Type[:\s]*([^\n]+)'],
                'modality': [r'Modality[:\s]*([^\n]+)'],
                'approval_date': [r'Approval[:\s]*(\d{1,2}\s+\w+\s+\d{4}|\d{4})', r'Approved[:\s]*([^\n]+)'],
                'signing_date': [r'Signing[:\s]*(\d{1,2}\s+\w+\s+\d{4}|\d{4})'],
                'closing_date': [r'Closing[:\s]*(\d{1,2}\s+\w+\s+\d{4}|\d{4})'],
                'financing_amount': [r'(\$[\d,\.]+\s*(?:million|billion)?)', r'Financing[:\s]*([\d,\.]+)', r'Amount[:\s]*([\d,\.]+)'],
                'borrower': [r'Borrower[:\s]*([^\n]+)'],
                'executing_agency': [r'Executing Agency[:\s]*([^\n]+)'],
                'implementing_agency': [r'Implementing Agency[:\s]*([^\n]+)'],
            }
            
            for field_name, patterns in field_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        if value and len(value) < 500:
                            setattr(project, field_name, value)
                            break
            
            # Extract description from specific elements
            desc_selectors = [
                '.field--name-body p',
                '.project-description',
                '.content-wrapper p',
                'article p',
                '.main-content p'
            ]
            
            for selector in desc_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    desc_parts = []
                    for el in elements[:3]:
                        text = el.text.strip()
                        if text and len(text) > 50:
                            desc_parts.append(text)
                    if desc_parts:
                        project.description = ' '.join(desc_parts)[:2000]
                        break
                except:
                    continue
            
            return project
            
        except Exception as e:
            print(f"Error fetching {project_url}: {e}")
            return None
    
    def scrape_all_projects(self, max_pages: int = 5, fetch_details: bool = True) -> List[Project]:
        """
        Scrape all projects from multiple pages
        """
        try:
            self._setup_driver()
            
            print("=" * 60)
            print("Starting ADB Projects Scraper")
            print("=" * 60)
            
            # Get project listings
            listings = self.get_projects_from_listing(max_pages=max_pages)
            print(f"\nFound {len(listings)} projects in listings")
            
            all_projects = []
            
            if fetch_details and listings:
                print("\nFetching detailed information for each project...")
                for i, listing in enumerate(listings):
                    url = listing.get('project_url', '')
                    if url:
                        print(f"  [{i+1}/{len(listings)}] {listing.get('title', 'Unknown')[:50]}...")
                        project = self.get_project_details(url)
                        if project:
                            # Merge listing data
                            if not project.title and listing.get('title'):
                                project.title = listing['title']
                            all_projects.append(project)
                        else:
                            project = Project(**{k: v for k, v in listing.items() if hasattr(Project, k)})
                            all_projects.append(project)
                        time.sleep(self.delay)
            else:
                for listing in listings:
                    project = Project(**{k: v for k, v in listing.items() if hasattr(Project, k)})
                    all_projects.append(project)
            
            self.projects = all_projects
            print(f"\nTotal projects scraped: {len(all_projects)}")
            return all_projects
            
        finally:
            self._close_driver()
    
    def scrape_project_by_id(self, project_id: str) -> Optional[Project]:
        """Scrape a specific project by its ID"""
        try:
            self._setup_driver()
            url = f"{self.PROJECTS_URL}/{project_id}"
            return self.get_project_details(url)
        finally:
            self._close_driver()
    
    def save_to_json(self, filename: str = "adb_projects.json"):
        """Save scraped projects to JSON file"""
        if not self.projects:
            print("No projects to save.")
            return
        
        data = [asdict(p) for p in self.projects]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(data)} projects to {filename}")
    
    def save_to_csv(self, filename: str = "adb_projects.csv"):
        """Save scraped projects to CSV file"""
        if not self.projects:
            print("No projects to save.")
            return
        
        data = [asdict(p) for p in self.projects]
        if not data:
            return
        
        fieldnames = list(data[0].keys())
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"Saved {len(data)} projects to {filename}")


def main():
    """Main function to run the scraper"""
    print("=" * 60)
    print("ADB Projects Scraper (with Cloudflare bypass)")
    print("=" * 60)
    
    scraper = ADBScraper(headless=True, delay=2.0)
    
    try:
        # Scrape projects
        projects = scraper.scrape_all_projects(max_pages=3, fetch_details=True)
        
        if projects:
            scraper.save_to_json("adb_projects.json")
            scraper.save_to_csv("adb_projects.csv")
            
            print("\n" + "=" * 60)
            print("Sample of scraped projects:")
            print("=" * 60)
            
            for i, project in enumerate(projects[:5]):
                print(f"\n--- Project {i + 1} ---")
                print(f"ID: {project.project_id}")
                print(f"Title: {project.title}")
                print(f"Country: {project.country}")
                print(f"Sector: {project.sector}")
                print(f"Status: {project.status}")
                print(f"Approval Date: {project.approval_date}")
                print(f"Financing: {project.financing_amount}")
                print(f"URL: {project.project_url}")
                if project.description:
                    print(f"Description: {project.description[:150]}...")
        else:
            print("\nNo projects were scraped.")
            
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
