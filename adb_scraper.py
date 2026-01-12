"""
ADB (Asian Development Bank) Projects Scraper
Extracts project information from https://www.adb.org/projects

Uses Selenium for browser automation to bypass Cloudflare protection.
"""

import json
import csv
import time
import re
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, asdict, field

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Selenium not installed. Run: pip install selenium webdriver-manager")

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False


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
    """Scraper for Asian Development Bank projects using Selenium"""
    
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
        """Setup Chrome WebDriver with appropriate options"""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is required. Install with: pip install selenium")
        
        options = Options()
        
        if self.headless:
            options.add_argument('--headless=new')
        
        # Anti-detection options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--start-maximized')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Exclude automation flags
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            if WEBDRIVER_MANAGER_AVAILABLE:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
            
            # Additional anti-detection
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            print("Trying Firefox as fallback...")
            try:
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                fox_options = FirefoxOptions()
                if self.headless:
                    fox_options.add_argument('--headless')
                self.driver = webdriver.Firefox(options=fox_options)
            except Exception as e2:
                raise RuntimeError(f"Could not initialize any browser: {e2}")
    
    def _close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def _wait_for_page_load(self, timeout: int = 30):
        """Wait for page to fully load"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(self.delay)  # Additional wait for dynamic content
        except TimeoutException:
            print("Page load timeout, continuing anyway...")
    
    def _extract_text(self, element, selector: str, default: str = "") -> str:
        """Safely extract text from an element"""
        try:
            el = element.find_element(By.CSS_SELECTOR, selector)
            return el.text.strip()
        except NoSuchElementException:
            return default
    
    def get_projects_from_listing(self, max_pages: int = 10) -> List[dict]:
        """
        Fetch projects from the ADB projects listing page
        
        Args:
            max_pages: Maximum number of pages to scrape
            
        Returns:
            List of project dictionaries with basic info
        """
        if not self.driver:
            self._setup_driver()
        
        all_projects = []
        
        print(f"Navigating to {self.PROJECTS_URL}...")
        self.driver.get(self.PROJECTS_URL)
        self._wait_for_page_load()
        
        # Wait for Cloudflare challenge if present
        time.sleep(5)
        
        for page in range(max_pages):
            print(f"\nScraping page {page + 1}...")
            
            # Wait for project items to load
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.item-list, .view-content, .search-results, [class*="project"], main'))
                )
            except TimeoutException:
                print("Timeout waiting for project list. Saving page source for debugging...")
                with open(f"debug_page_{page}.html", "w") as f:
                    f.write(self.driver.page_source)
            
            # Try multiple selectors for project items
            selectors = [
                '.item-list .views-row',
                '.view-content .views-row',
                '.search-result-item',
                '[class*="project-item"]',
                '.views-row',
                'article',
                '.node--type-project',
            ]
            
            project_items = []
            for selector in selectors:
                try:
                    items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if items:
                        project_items = items
                        print(f"  Found {len(items)} items using selector: {selector}")
                        break
                except:
                    continue
            
            if not project_items:
                print("  No project items found on this page.")
                # Save page source for debugging
                with open(f"debug_page_{page}.html", "w") as f:
                    f.write(self.driver.page_source)
                
                # Try to find any links to projects
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/projects/"]')
                    print(f"  Found {len(links)} project links")
                    for link in links[:20]:
                        href = link.get_attribute('href')
                        text = link.text.strip()
                        if href and '/projects/' in href and text:
                            # Extract project ID from URL
                            match = re.search(r'/projects/(\d+)', href)
                            proj_id = match.group(1) if match else ""
                            all_projects.append({
                                'project_id': proj_id,
                                'title': text,
                                'project_url': href
                            })
                except Exception as e:
                    print(f"  Error finding project links: {e}")
                break
            
            # Parse each project item
            for item in project_items:
                try:
                    project_data = self._parse_listing_item(item)
                    if project_data:
                        all_projects.append(project_data)
                except Exception as e:
                    print(f"  Error parsing item: {e}")
            
            print(f"  Collected {len(all_projects)} projects so far")
            
            # Try to go to next page
            if not self._go_to_next_page():
                print("No more pages available.")
                break
            
            time.sleep(self.delay)
        
        return all_projects
    
    def _parse_listing_item(self, item) -> Optional[dict]:
        """Parse a project item from the listing"""
        data = {}
        
        # Try to find title and link
        try:
            link = item.find_element(By.CSS_SELECTOR, 'a')
            data['title'] = link.text.strip()
            data['project_url'] = link.get_attribute('href')
        except:
            try:
                title_el = item.find_element(By.CSS_SELECTOR, 'h2, h3, h4, .title')
                data['title'] = title_el.text.strip()
            except:
                pass
        
        # Extract project ID from URL or text
        if 'project_url' in data:
            match = re.search(r'/projects/(\d+)', data['project_url'])
            if match:
                data['project_id'] = match.group(1)
        
        # Try to extract other fields
        text = item.text
        
        # Country
        country_match = re.search(r'Country[:\s]+([A-Za-z,\s]+?)(?:\n|$)', text)
        if country_match:
            data['country'] = country_match.group(1).strip()
        
        # Sector
        sector_match = re.search(r'Sector[:\s]+([A-Za-z,\s]+?)(?:\n|$)', text)
        if sector_match:
            data['sector'] = sector_match.group(1).strip()
        
        # Status
        status_match = re.search(r'Status[:\s]+([A-Za-z\s]+?)(?:\n|$)', text)
        if status_match:
            data['status'] = status_match.group(1).strip()
        
        return data if data.get('title') or data.get('project_id') else None
    
    def _go_to_next_page(self) -> bool:
        """Try to navigate to the next page"""
        try:
            # Try various next page selectors
            next_selectors = [
                'a.pager__link--next',
                '.pager-next a',
                'a[rel="next"]',
                '.pagination .next a',
                'li.next a',
                'a:contains("Next")',
                '[aria-label="Next page"]',
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if next_btn.is_displayed() and next_btn.is_enabled():
                        next_btn.click()
                        self._wait_for_page_load()
                        return True
                except:
                    continue
            
            # Try clicking by link text
            try:
                next_btn = self.driver.find_element(By.LINK_TEXT, 'Next')
                next_btn.click()
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
        
        Args:
            project_url: URL of the project detail page
            
        Returns:
            Project object with all available details
        """
        if not self.driver:
            self._setup_driver()
        
        try:
            self.driver.get(project_url)
            self._wait_for_page_load()
            
            project = Project(project_url=project_url)
            
            # Extract project ID from URL
            match = re.search(r'/projects/(\d+)', project_url)
            if match:
                project.project_id = match.group(1)
            
            # Extract title
            try:
                title = self.driver.find_element(By.CSS_SELECTOR, 'h1, .page-title')
                project.title = title.text.strip()
            except:
                pass
            
            # Get all text content for pattern matching
            page_text = self.driver.find_element(By.TAG_NAME, 'body').text
            
            # Extract fields using patterns
            field_patterns = {
                'project_id': [r'Project Number[:\s]+(\d+)', r'Project No\.[:\s]+(\d+)'],
                'country': [r'Country[:\s]+([^\n]+)', r'Countries[:\s]+([^\n]+)'],
                'region': [r'Region[:\s]+([^\n]+)'],
                'sector': [r'Sector[:\s]+([^\n]+)'],
                'subsector': [r'Subsector[:\s]+([^\n]+)'],
                'status': [r'Status[:\s]+([^\n]+)', r'Project Status[:\s]+([^\n]+)'],
                'project_type': [r'Project Type[:\s]+([^\n]+)', r'Type[:\s]+([^\n]+)'],
                'approval_date': [r'Approval Date[:\s]+([^\n]+)', r'Approved[:\s]+([^\n]+)'],
                'signing_date': [r'Signing Date[:\s]+([^\n]+)'],
                'closing_date': [r'Closing Date[:\s]+([^\n]+)'],
                'effectivity_date': [r'Effectivity Date[:\s]+([^\n]+)'],
                'financing_amount': [r'Financing[:\s]+([^\n]+)', r'Amount[:\s]+([^\n]+)', r'\$[\d,\.]+\s*million'],
                'borrower': [r'Borrower[:\s]+([^\n]+)'],
                'executing_agency': [r'Executing Agency[:\s]+([^\n]+)'],
                'implementing_agency': [r'Implementing Agency[:\s]+([^\n]+)'],
            }
            
            for field_name, patterns in field_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        value = match.group(1) if match.lastindex else match.group(0)
                        setattr(project, field_name, value.strip())
                        break
            
            # Extract description
            try:
                desc_selectors = [
                    '.field--name-body',
                    '.project-description',
                    '.description',
                    'article .content p',
                    '.main-content p'
                ]
                for selector in desc_selectors:
                    try:
                        desc = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if desc.text.strip():
                            project.description = desc.text.strip()[:2000]
                            break
                    except:
                        continue
            except:
                pass
            
            # Try to extract from structured data (tables)
            try:
                tables = self.driver.find_elements(By.TAG_NAME, 'table')
                for table in tables:
                    rows = table.find_elements(By.TAG_NAME, 'tr')
                    for row in rows:
                        cells = row.find_elements(By.CSS_SELECTOR, 'td, th')
                        if len(cells) >= 2:
                            label = cells[0].text.strip().lower()
                            value = cells[1].text.strip()
                            
                            if 'project' in label and ('number' in label or 'id' in label):
                                project.project_id = value
                            elif 'country' in label:
                                project.country = value
                            elif 'sector' in label and 'sub' not in label:
                                project.sector = value
                            elif 'subsector' in label:
                                project.subsector = value
                            elif 'status' in label:
                                project.status = value
                            elif 'approval' in label:
                                project.approval_date = value
                            elif 'signing' in label:
                                project.signing_date = value
                            elif 'closing' in label:
                                project.closing_date = value
                            elif 'financing' in label or 'amount' in label:
                                project.financing_amount = value
                            elif 'borrower' in label:
                                project.borrower = value
                            elif 'executing' in label:
                                project.executing_agency = value
            except:
                pass
            
            return project
            
        except Exception as e:
            print(f"Error fetching project details from {project_url}: {e}")
            return None
    
    def scrape_all_projects(self, max_pages: int = 10, fetch_details: bool = True) -> List[Project]:
        """
        Scrape all projects from multiple pages
        
        Args:
            max_pages: Maximum number of pages to scrape
            fetch_details: Whether to fetch detailed info for each project
            
        Returns:
            List of Project objects
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
                        print(f"  [{i+1}/{len(listings)}] Fetching: {listing.get('title', 'Unknown')[:50]}...")
                        project = self.get_project_details(url)
                        if project:
                            # Merge listing data with detailed data
                            for key, value in listing.items():
                                if value and not getattr(project, key, None):
                                    if hasattr(project, key):
                                        setattr(project, key, value)
                            all_projects.append(project)
                        time.sleep(self.delay)
                    else:
                        # Create project from listing data
                        project = Project(**{k: v for k, v in listing.items() if hasattr(Project, k)})
                        all_projects.append(project)
            else:
                # Just use listing data
                for listing in listings:
                    project = Project(**{k: v for k, v in listing.items() if hasattr(Project, k)})
                    all_projects.append(project)
            
            self.projects = all_projects
            print(f"\nTotal projects scraped: {len(all_projects)}")
            return all_projects
            
        finally:
            self._close_driver()
    
    def scrape_project_by_id(self, project_id: str) -> Optional[Project]:
        """
        Scrape a specific project by its ID
        
        Args:
            project_id: The ADB project number/ID
            
        Returns:
            Project object or None
        """
        try:
            self._setup_driver()
            url = f"{self.PROJECTS_URL}/{project_id}"
            return self.get_project_details(url)
        finally:
            self._close_driver()
    
    def save_to_json(self, filename: str = "adb_projects.json"):
        """Save scraped projects to JSON file"""
        if not self.projects:
            print("No projects to save. Run scrape_all_projects() first.")
            return
        
        data = [asdict(p) for p in self.projects]
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(data)} projects to {filename}")
    
    def save_to_csv(self, filename: str = "adb_projects.csv"):
        """Save scraped projects to CSV file"""
        if not self.projects:
            print("No projects to save. Run scrape_all_projects() first.")
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
    print("ADB Projects Scraper")
    print("=" * 60)
    print("\nThis scraper uses Selenium to bypass Cloudflare protection.")
    print("Make sure you have Chrome or Firefox installed.\n")
    
    # Initialize scraper
    scraper = ADBScraper(headless=True, delay=2.0)
    
    try:
        # Scrape projects (adjust max_pages as needed)
        projects = scraper.scrape_all_projects(max_pages=3, fetch_details=True)
        
        if projects:
            # Save to both JSON and CSV
            scraper.save_to_json("adb_projects.json")
            scraper.save_to_csv("adb_projects.csv")
            
            # Print sample of scraped data
            print("\n" + "=" * 60)
            print("Sample of scraped projects:")
            print("=" * 60)
            
            for i, project in enumerate(projects[:3]):
                print(f"\n--- Project {i + 1} ---")
                print(f"ID: {project.project_id}")
                print(f"Title: {project.title}")
                print(f"Country: {project.country}")
                print(f"Region: {project.region}")
                print(f"Sector: {project.sector}")
                print(f"Status: {project.status}")
                print(f"Approval Date: {project.approval_date}")
                print(f"Financing: {project.financing_amount}")
                print(f"Borrower: {project.borrower}")
                print(f"URL: {project.project_url}")
                if project.description:
                    print(f"Description: {project.description[:200]}...")
        else:
            print("\nNo projects were scraped.")
            print("The website may have changed its structure or blocking mechanism.")
            
    except Exception as e:
        print(f"\nError during scraping: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure Chrome or Firefox is installed")
        print("2. Try running with headless=False to see what's happening")
        print("3. The website may require manual CAPTCHA solving")


if __name__ == "__main__":
    main()
