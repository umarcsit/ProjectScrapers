"""
ADB Consulting Opportunities (CSRN) Scraper
Extracts consulting services recruitment notices from:
https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN_HOME_PAGE

This scraper extracts:
- Project ID, Title, Country, Sector
- Consulting Type (Firm/Individual)
- Deadline, Duration, Budget
- Selection Method, Engagement Type
- And more...
"""

import json
import csv
import time
import re
import os
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict, field

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠ Selenium not installed. Run: pip install selenium webdriver-manager")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


@dataclass
class ConsultingOpportunity:
    """Data class for ADB Consulting Opportunities (CSRN)"""
    csrn_id: str = ""
    title: str = ""
    project_name: str = ""
    project_number: str = ""
    country: str = ""
    sector: str = ""
    consulting_type: str = ""  # Firm or Individual
    engagement_type: str = ""
    selection_method: str = ""
    budget_range: str = ""
    duration: str = ""
    deadline: str = ""
    published_date: str = ""
    status: str = ""
    executing_agency: str = ""
    description: str = ""
    terms_of_reference_url: str = ""
    detail_url: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ADBConsultingScraper:
    """
    Scraper for ADB Consulting Opportunities (CSRN)
    URL: https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN_HOME_PAGE
    """
    
    BASE_URL = "https://selfservice.adb.org"
    CSRN_URL = "https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN_HOME_PAGE"
    
    def __init__(self, headless: bool = True, delay: float = 2.0):
        """
        Initialize the scraper
        
        Args:
            headless: Run browser in headless mode (no GUI)
            delay: Delay between page requests in seconds
        """
        self.headless = headless
        self.delay = delay
        self.driver = None
        self.opportunities: List[ConsultingOpportunity] = []
    
    def _setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium not installed. Run: pip install selenium webdriver-manager")
        
        options = Options()
        
        if self.headless:
            options.add_argument('--headless=new')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except:
            self.driver = webdriver.Chrome(options=options)
        
        self.driver.implicitly_wait(10)
        print("✓ Browser initialized")
    
    def _close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def _wait_for_element(self, by, value, timeout=20):
        """Wait for element to be present"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            return None
    
    def _parse_title_for_details(self, title: str) -> dict:
        """Extract project details from title string"""
        details = {}
        
        # Extract project number from title (format: LOAN-XXXX, GRANT-XXXX, TA-XXXX)
        proj_match = re.search(r'(LOAN|GRANT|TA|L|G)-?(\d+)', title, re.IGNORECASE)
        if proj_match:
            details['project_type'] = proj_match.group(1).upper()
            details['project_number'] = proj_match.group(2)
        
        # Extract ADB project ID (format: XXXXX-XXX in parentheses)
        adb_id_match = re.search(r'\((\d{5}-\d{3})\)', title)
        if adb_id_match:
            details['project_id'] = adb_id_match.group(1)
        
        # Extract country codes (3-letter codes like REG, CAM, PRC, VIE, etc.)
        country_codes = {
            'REG': 'Regional',
            'CAM': 'Cambodia',
            'PRC': 'China',
            'VIE': 'Vietnam',
            'IND': 'India',
            'INO': 'Indonesia',
            'PHI': 'Philippines',
            'BAN': 'Bangladesh',
            'PAK': 'Pakistan',
            'SRI': 'Sri Lanka',
            'NEP': 'Nepal',
            'MYA': 'Myanmar',
            'THA': 'Thailand',
            'LAO': 'Lao PDR',
            'MON': 'Mongolia',
            'UZB': 'Uzbekistan',
            'KAZ': 'Kazakhstan',
            'KGZ': 'Kyrgyz Republic',
            'TAJ': 'Tajikistan',
            'TKM': 'Turkmenistan',
            'AFG': 'Afghanistan',
            'ARM': 'Armenia',
            'AZE': 'Azerbaijan',
            'GEO': 'Georgia',
            'PNG': 'Papua New Guinea',
            'FIJ': 'Fiji',
            'SAM': 'Samoa',
            'TON': 'Tonga',
            'VAN': 'Vanuatu',
            'SOL': 'Solomon Islands',
            'TIM': 'Timor-Leste',
            'MLD': 'Maldives',
            'BHU': 'Bhutan',
        }
        
        country_match = re.search(r'\b([A-Z]{3}):', title)
        if country_match:
            code = country_match.group(1)
            details['country'] = country_codes.get(code, code)
        
        return details
    
    def scrape_opportunities(self, max_pages: int = 10, fetch_details: bool = False) -> List[ConsultingOpportunity]:
        """
        Scrape consulting opportunities from ADB CSRN portal
        
        Args:
            max_pages: Maximum pages to scrape
            fetch_details: Whether to fetch detailed info for each opportunity
            
        Returns:
            List of ConsultingOpportunity objects
        """
        if not SELENIUM_AVAILABLE:
            print("❌ Selenium not available. Install with: pip install selenium webdriver-manager")
            return []
        
        try:
            self._setup_driver()
            
            print(f"\n🌐 Navigating to CSRN portal...")
            print(f"   URL: {self.CSRN_URL}")
            self.driver.get(self.CSRN_URL)
            
            # Wait for page to load
            print("⏳ Waiting for page to load...")
            time.sleep(5)
            
            # Wait for the results table
            results_table = self._wait_for_element(By.ID, "atResults")
            
            if not results_table:
                print("⚠ Could not find results table, trying alternative selectors...")
                results_table = self._wait_for_element(By.CSS_SELECTOR, "table[id*='Results'], table.x1h")
            
            all_opportunities = []
            page_num = 1
            
            while page_num <= max_pages:
                print(f"\n📄 Scraping page {page_num}...")
                
                # Parse current page
                page_opportunities = self._parse_results_page()
                
                # Filter out navigation elements
                valid_opportunities = [
                    opp for opp in page_opportunities 
                    if opp.get('title') and 
                    not opp.get('title', '').startswith('Next') and
                    not opp.get('title', '').startswith('Previous') and
                    len(opp.get('title', '')) > 10
                ]
                
                if not valid_opportunities:
                    print("   No more valid opportunities found.")
                    break
                
                all_opportunities.extend(valid_opportunities)
                print(f"   ✓ Found {len(valid_opportunities)} opportunities")
                print(f"   📊 Total so far: {len(all_opportunities)}")
                
                # Try to go to next page
                if not self._go_to_next_page():
                    print("   ℹ No more pages available.")
                    break
                
                page_num += 1
                time.sleep(self.delay)
            
            # Convert to ConsultingOpportunity objects
            self.opportunities = []
            for opp_dict in all_opportunities:
                # Parse additional details from title
                title_details = self._parse_title_for_details(opp_dict.get('title', ''))
                opp_dict.update({k: v for k, v in title_details.items() if not opp_dict.get(k)})
                
                opp = ConsultingOpportunity(
                    csrn_id=opp_dict.get('csrn_id', ''),
                    title=opp_dict.get('title', ''),
                    project_name=opp_dict.get('project_name', ''),
                    project_number=opp_dict.get('project_number', opp_dict.get('project_id', '')),
                    country=opp_dict.get('country', ''),
                    sector=opp_dict.get('sector', ''),
                    consulting_type=opp_dict.get('consulting_type', ''),
                    engagement_type=opp_dict.get('engagement_type', ''),
                    selection_method=opp_dict.get('selection_method', ''),
                    budget_range=opp_dict.get('budget_range', ''),
                    duration=opp_dict.get('duration', ''),
                    deadline=opp_dict.get('deadline', ''),
                    published_date=opp_dict.get('published_date', ''),
                    status=opp_dict.get('status', 'Open'),
                    executing_agency=opp_dict.get('executing_agency', ''),
                    description=opp_dict.get('description', ''),
                    detail_url=opp_dict.get('detail_url', ''),
                )
                self.opportunities.append(opp)
            
            # Fetch additional details if requested
            if fetch_details and self.opportunities:
                print(f"\n📋 Fetching detailed information...")
                for i, opp in enumerate(self.opportunities[:20]):  # Limit to first 20 for speed
                    if opp.detail_url and 'adb.org/projects' in opp.detail_url:
                        print(f"   [{i+1}] Fetching details for: {opp.title[:50]}...")
                        self._fetch_opportunity_details(opp)
                        time.sleep(1)
            
            print(f"\n✅ Total opportunities scraped: {len(self.opportunities)}")
            return self.opportunities
            
        except Exception as e:
            print(f"\n❌ Error during scraping: {e}")
            import traceback
            traceback.print_exc()
            return self.opportunities
            
        finally:
            self._close_driver()
    
    def _parse_results_page(self) -> List[dict]:
        """Parse the results table on current page"""
        opportunities = []
        
        try:
            # Method 1: Parse using Selenium
            table = self.driver.find_element(By.ID, "atResults")
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 2:
                        continue
                    
                    opp = {}
                    row_text = row.text
                    
                    # Skip pagination rows
                    if 'Next' in row_text and len(row_text) < 20:
                        continue
                    if 'Previous' in row_text and len(row_text) < 20:
                        continue
                    
                    # Find all links in the row
                    links = row.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        href = link.get_attribute('href') or ''
                        text = link.text.strip()
                        
                        # Skip navigation links
                        if text in ['Next', 'Previous', 'Next 25', 'Previous 25', '']:
                            continue
                        
                        # Main title link
                        if text and len(text) > 15:
                            opp['title'] = text
                            opp['detail_url'] = href
                    
                    # Extract consulting type from icon or text
                    if 'Firm' in row_text or 'firm' in row.get_attribute('innerHTML').lower():
                        opp['consulting_type'] = 'Firm'
                    elif 'Individual' in row_text or 'individual' in row.get_attribute('innerHTML').lower():
                        opp['consulting_type'] = 'Individual'
                    
                    # Try to extract deadline from cells
                    for cell in cells:
                        cell_text = cell.text.strip()
                        # Check if it looks like a date
                        if re.match(r'\d{1,2}[-/]\w{3}[-/]\d{4}', cell_text):
                            opp['deadline'] = cell_text
                        elif re.match(r'\d{4}[-/]\d{2}[-/]\d{2}', cell_text):
                            opp['deadline'] = cell_text
                    
                    if opp.get('title'):
                        opportunities.append(opp)
                        
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue
            
        except Exception as e:
            print(f"   ⚠ Error parsing table: {e}")
            
            # Method 2: Try BeautifulSoup parsing
            if BS4_AVAILABLE:
                try:
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    table = soup.find(id='atResults')
                    
                    if table:
                        for row in table.find_all('tr'):
                            cells = row.find_all('td')
                            if len(cells) < 2:
                                continue
                            
                            opp = {}
                            row_text = row.get_text()
                            
                            # Find links
                            for link in row.find_all('a'):
                                text = link.get_text(strip=True)
                                href = link.get('href', '')
                                
                                if text and len(text) > 15 and text not in ['Next', 'Previous', 'Next 25']:
                                    opp['title'] = text
                                    opp['detail_url'] = href if href.startswith('http') else self.BASE_URL + href
                            
                            if 'Firm' in row_text:
                                opp['consulting_type'] = 'Firm'
                            elif 'Individual' in row_text:
                                opp['consulting_type'] = 'Individual'
                            
                            if opp.get('title'):
                                opportunities.append(opp)
                except Exception:
                    pass
        
        return opportunities
    
    def _go_to_next_page(self) -> bool:
        """Try to navigate to next page"""
        try:
            # Try various selectors for next button
            next_selectors = [
                "//a[contains(text(), 'Next')]",
                "//img[@title='Next']/parent::a",
                "//a[@title='Next']",
                "//td[contains(@class, 'xh')]//a[contains(text(), 'Next')]",
            ]
            
            for xpath in next_selectors:
                try:
                    next_btn = self.driver.find_element(By.XPATH, xpath)
                    if next_btn.is_displayed():
                        # Scroll to element
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
                        time.sleep(0.5)
                        next_btn.click()
                        time.sleep(3)
                        return True
                except:
                    continue
            
            # Try CSS selectors
            css_selectors = [
                "a[title*='Next']",
                "a.xh[href*='Next']",
                "img[alt='Next']",
            ]
            
            for css in css_selectors:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, css)
                    if next_btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", next_btn)
                        time.sleep(3)
                        return True
                except:
                    continue
            
            return False
            
        except Exception:
            return False
    
    def _fetch_opportunity_details(self, opportunity: ConsultingOpportunity):
        """Fetch additional details for an opportunity"""
        if not opportunity.detail_url:
            return
        
        try:
            self.driver.get(opportunity.detail_url)
            time.sleep(2)
            
            page_text = self.driver.find_element(By.TAG_NAME, 'body').text
            
            # Extract additional fields
            patterns = {
                'sector': r'Sector[:\s]*([^\n]+)',
                'country': r'Country[:\s]*([^\n]+)',
                'executing_agency': r'Executing Agency[:\s]*([^\n]+)',
                'description': r'Description[:\s]*([^\n]+)',
            }
            
            for field, pattern in patterns.items():
                if not getattr(opportunity, field):
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        setattr(opportunity, field, match.group(1).strip()[:500])
            
        except Exception:
            pass
    
    def save_to_json(self, filename: str = "adb_consulting_opportunities.json"):
        """Save opportunities to JSON file"""
        if not self.opportunities:
            print("❌ No opportunities to save")
            return
        
        data = [asdict(opp) for opp in self.opportunities]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {len(data)} opportunities to {filename}")
    
    def save_to_csv(self, filename: str = "adb_consulting_opportunities.csv"):
        """Save opportunities to CSV file"""
        if not self.opportunities:
            print("❌ No opportunities to save")
            return
        
        data = [asdict(opp) for opp in self.opportunities]
        fieldnames = list(data[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"✓ Saved {len(data)} opportunities to {filename}")
    
    def load_from_json(self, filename: str) -> List[ConsultingOpportunity]:
        """Load opportunities from JSON file"""
        if not os.path.exists(filename):
            print(f"❌ File not found: {filename}")
            return []
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.opportunities = [
                ConsultingOpportunity(**item) for item in data
            ]
            print(f"✓ Loaded {len(self.opportunities)} opportunities from {filename}")
            return self.opportunities
        except Exception as e:
            print(f"❌ Error loading JSON: {e}")
            return []
    
    def print_summary(self):
        """Print summary of scraped opportunities"""
        if not self.opportunities:
            print("❌ No opportunities loaded")
            return
        
        print("\n" + "=" * 70)
        print(f"📊 CONSULTING OPPORTUNITIES SUMMARY: {len(self.opportunities)} total")
        print("=" * 70)
        
        # Count by type
        types = {}
        countries = {}
        
        for opp in self.opportunities:
            if opp.consulting_type:
                types[opp.consulting_type] = types.get(opp.consulting_type, 0) + 1
            if opp.country:
                countries[opp.country] = countries.get(opp.country, 0) + 1
        
        if types:
            print("\n📌 By Consulting Type:")
            for t, count in sorted(types.items(), key=lambda x: -x[1]):
                print(f"   • {t}: {count}")
        
        if countries:
            print("\n🌍 By Country:")
            for country, count in sorted(countries.items(), key=lambda x: -x[1])[:15]:
                print(f"   • {country}: {count}")
        
        print("\n" + "-" * 70)
        print("📋 Sample Opportunities:")
        print("-" * 70)
        
        # Filter for valid opportunities
        valid_opps = [o for o in self.opportunities if len(o.title) > 20]
        
        for i, opp in enumerate(valid_opps[:10]):
            print(f"\n[{i+1}] {opp.title[:80]}...")
            print(f"    Type: {opp.consulting_type or 'N/A'}")
            print(f"    Country: {opp.country or 'N/A'}")
            print(f"    Project #: {opp.project_number or 'N/A'}")
            if opp.deadline:
                print(f"    Deadline: {opp.deadline}")
            if opp.detail_url:
                print(f"    URL: {opp.detail_url[:60]}...")


def main():
    """Main function to run the scraper"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     ADB CONSULTING OPPORTUNITIES SCRAPER (CSRN)                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  Source: https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=          ║
║          XXCRS_CSRN_HOME_PAGE                                        ║
║                                                                      ║
║  Extracts: Title, Project Number, Country, Consulting Type,         ║
║            Deadline, Budget, Selection Method, and more...          ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize scraper
    scraper = ADBConsultingScraper(headless=True, delay=2.0)
    
    try:
        # Scrape opportunities
        opportunities = scraper.scrape_opportunities(max_pages=10, fetch_details=False)
        
        if opportunities:
            # Save results
            scraper.save_to_json("adb_consulting_opportunities.json")
            scraper.save_to_csv("adb_consulting_opportunities.csv")
            
            # Print summary
            scraper.print_summary()
        else:
            print("\n⚠ No opportunities were scraped.")
            print("   The page structure may have changed.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
