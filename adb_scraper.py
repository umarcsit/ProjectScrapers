"""
ADB Consulting Opportunities (CSRN) Scraper
Extracts consulting services recruitment notices from:
https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN_HOME_PAGE

This scraper extracts FULL details including:
- Project ID, Title, Country, Sector
- Consulting Type (Firm/Individual)
- Deadline, Duration, Budget
- Selection Method, Engagement Type
- FULL Project Description
- Terms of Reference
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
    """Data class for ADB Consulting Opportunities (CSRN) with FULL details"""
    # Basic Info
    csrn_id: str = ""
    title: str = ""
    reference_number: str = ""
    
    # Project Info
    project_name: str = ""
    project_number: str = ""
    project_type: str = ""  # LOAN, GRANT, TA
    
    # Location
    country: str = ""
    region: str = ""
    
    # Classification
    sector: str = ""
    subsector: str = ""
    
    # Consulting Details
    consulting_type: str = ""  # Firm or Individual
    engagement_type: str = ""
    selection_method: str = ""
    consultant_source: str = ""  # International, National, etc.
    
    # Financial
    budget_range: str = ""
    estimated_cost: str = ""
    funding_source: str = ""
    
    # Timeline
    duration: str = ""
    deadline: str = ""
    published_date: str = ""
    contract_start_date: str = ""
    
    # Status
    status: str = ""
    
    # Organizations
    executing_agency: str = ""
    implementing_agency: str = ""
    
    # Full Description & TOR
    description: str = ""
    objectives: str = ""
    scope_of_work: str = ""
    deliverables: str = ""
    qualifications: str = ""
    terms_of_reference: str = ""
    terms_of_reference_url: str = ""
    
    # Links
    detail_url: str = ""
    project_page_url: str = ""
    
    # Metadata
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ADBConsultingScraper:
    """
    Scraper for ADB Consulting Opportunities (CSRN)
    URL: https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN_HOME_PAGE
    
    Fetches FULL project details including descriptions and TOR.
    """
    
    BASE_URL = "https://selfservice.adb.org"
    CSRN_URL = "https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN_HOME_PAGE"
    ADB_PROJECTS_URL = "https://www.adb.org/projects"
    
    # Country code mappings
    COUNTRY_CODES = {
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
        'COO': 'Cook Islands',
        'FSM': 'Micronesia',
        'KIR': 'Kiribati',
        'NAU': 'Nauru',
        'NIU': 'Niue',
        'PAL': 'Palau',
        'RMI': 'Marshall Islands',
        'TUV': 'Tuvalu',
    }
    
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
        
        # Extract project type and number (LOAN-XXXX, GRANT-XXXX, TA-XXXX)
        proj_match = re.search(r'(LOAN|GRANT|TA|L|G)-?(\d+)', title, re.IGNORECASE)
        if proj_match:
            ptype = proj_match.group(1).upper()
            if ptype == 'L':
                ptype = 'LOAN'
            elif ptype == 'G':
                ptype = 'GRANT'
            details['project_type'] = ptype
        
        # Extract ADB project ID (format: XXXXX-XXX in parentheses)
        adb_id_match = re.search(r'\((\d{5}-\d{3})\)', title)
        if adb_id_match:
            details['project_number'] = adb_id_match.group(1)
        
        # Extract country code
        country_match = re.search(r'\b([A-Z]{3}):', title)
        if country_match:
            code = country_match.group(1)
            details['country'] = self.COUNTRY_CODES.get(code, code)
        
        # Extract project name (text between country code and package description)
        name_match = re.search(r'[A-Z]{3}:\s*([^-]+?)(?:\s*-\s*|\s*\()', title)
        if name_match:
            details['project_name'] = name_match.group(1).strip()
        
        return details
    
    def _get_csrn_detail_page(self, row_element) -> Optional[str]:
        """Click on a row to get the detail page URL"""
        try:
            # Find clickable link in the row
            links = row_element.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute('href') or ''
                text = link.text.strip()
                
                # Skip navigation links
                if text in ['Next', 'Previous', 'Next 25', 'Previous 25', '']:
                    continue
                
                # Click to view details
                if 'CsrnId' in href or 'view_csrn' in href:
                    return href
                
            return None
        except:
            return None
    
    def scrape_opportunities(self, max_pages: int = 10, fetch_details: bool = True) -> List[ConsultingOpportunity]:
        """
        Scrape consulting opportunities from ADB CSRN portal
        
        Args:
            max_pages: Maximum pages to scrape
            fetch_details: Whether to fetch FULL detailed info for each opportunity
            
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
                print("⚠ Could not find results table")
                return []
            
            all_opportunities = []
            page_num = 1
            
            while page_num <= max_pages:
                print(f"\n📄 Scraping page {page_num}...")
                
                # Parse current page - get basic info and detail URLs
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
            
            print(f"\n📋 Processing {len(all_opportunities)} opportunities...")
            
            # Convert to ConsultingOpportunity objects and fetch details
            self.opportunities = []
            for i, opp_dict in enumerate(all_opportunities):
                # Parse additional details from title
                title_details = self._parse_title_for_details(opp_dict.get('title', ''))
                opp_dict.update({k: v for k, v in title_details.items() if not opp_dict.get(k)})
                
                opp = ConsultingOpportunity(
                    csrn_id=opp_dict.get('csrn_id', ''),
                    title=opp_dict.get('title', ''),
                    reference_number=opp_dict.get('reference_number', ''),
                    project_name=opp_dict.get('project_name', ''),
                    project_number=opp_dict.get('project_number', ''),
                    project_type=opp_dict.get('project_type', ''),
                    country=opp_dict.get('country', ''),
                    sector=opp_dict.get('sector', ''),
                    consulting_type=opp_dict.get('consulting_type', ''),
                    deadline=opp_dict.get('deadline', ''),
                    detail_url=opp_dict.get('detail_url', ''),
                    status='Open',
                )
                
                # Fetch full details if requested
                if fetch_details and opp.detail_url:
                    print(f"   [{i+1}/{len(all_opportunities)}] Fetching details: {opp.title[:50]}...")
                    self._fetch_full_details(opp)
                    time.sleep(1)  # Be respectful to the server
                
                self.opportunities.append(opp)
            
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
            table = self.driver.find_element(By.ID, "atResults")
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 2:
                        continue
                    
                    opp = {}
                    row_text = row.text
                    row_html = row.get_attribute('innerHTML')
                    
                    # Skip pagination rows
                    if ('Next' in row_text or 'Previous' in row_text) and len(row_text) < 30:
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
                            
                            # Extract CSRN ID from href
                            csrn_match = re.search(r'CsrnId[=:](\d+)', href)
                            if csrn_match:
                                opp['csrn_id'] = csrn_match.group(1)
                    
                    # Extract consulting type
                    if 'Firm' in row_text or 'imgFirm' in row_html:
                        opp['consulting_type'] = 'Firm'
                    elif 'Individual' in row_text or 'imgIndividual' in row_html:
                        opp['consulting_type'] = 'Individual'
                    
                    # Try to extract deadline from cells
                    for cell in cells:
                        cell_text = cell.text.strip()
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
        
        return opportunities
    
    def _fetch_full_details(self, opportunity: ConsultingOpportunity):
        """Fetch FULL detailed information for an opportunity"""
        if not opportunity.detail_url:
            return
        
        try:
            # Navigate to detail page
            self.driver.get(opportunity.detail_url)
            time.sleep(3)
            
            # Get page source for parsing
            page_source = self.driver.page_source
            page_text = self.driver.find_element(By.TAG_NAME, 'body').text
            
            # Use BeautifulSoup for better parsing if available
            if BS4_AVAILABLE:
                soup = BeautifulSoup(page_source, 'html.parser')
                self._parse_detail_page_bs4(opportunity, soup, page_text)
            else:
                self._parse_detail_page_selenium(opportunity, page_text)
            
            # Also try to get ADB project page details if available
            if opportunity.project_number and not opportunity.description:
                project_url = f"https://www.adb.org/projects/{opportunity.project_number}/main"
                self._fetch_adb_project_details(opportunity, project_url)
            
        except Exception as e:
            print(f"      ⚠ Error fetching details: {e}")
    
    def _parse_detail_page_bs4(self, opp: ConsultingOpportunity, soup: BeautifulSoup, page_text: str):
        """Parse detail page using BeautifulSoup"""
        
        # Find all table rows and extract key-value pairs
        for row in soup.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                
                # Map labels to fields
                if 'project name' in label or 'project title' in label:
                    opp.project_name = value
                elif 'project number' in label or 'project no' in label:
                    opp.project_number = value
                elif 'country' in label:
                    opp.country = value
                elif 'sector' in label and 'sub' not in label:
                    opp.sector = value
                elif 'subsector' in label:
                    opp.subsector = value
                elif 'consultant type' in label or 'consulting type' in label:
                    opp.consulting_type = value
                elif 'engagement type' in label:
                    opp.engagement_type = value
                elif 'selection method' in label:
                    opp.selection_method = value
                elif 'consultant source' in label or 'source' in label:
                    opp.consultant_source = value
                elif 'budget' in label or 'estimated cost' in label:
                    if not opp.budget_range:
                        opp.budget_range = value
                    opp.estimated_cost = value
                elif 'duration' in label:
                    opp.duration = value
                elif 'deadline' in label or 'submission' in label:
                    opp.deadline = value
                elif 'publish' in label or 'posted' in label:
                    opp.published_date = value
                elif 'executing agency' in label:
                    opp.executing_agency = value
                elif 'implementing agency' in label:
                    opp.implementing_agency = value
                elif 'funding' in label:
                    opp.funding_source = value
                elif 'status' in label:
                    opp.status = value
        
        # Extract description sections
        self._extract_description_sections(opp, page_text, soup)
        
        # Find TOR download link
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = link.get_text(strip=True).lower()
            if 'tor' in text or 'terms of reference' in text or '.pdf' in href.lower():
                opp.terms_of_reference_url = href if href.startswith('http') else self.BASE_URL + href
                break
    
    def _parse_detail_page_selenium(self, opp: ConsultingOpportunity, page_text: str):
        """Parse detail page using regex patterns"""
        
        patterns = {
            'project_name': [r'Project Name[:\s]*([^\n]+)', r'Project Title[:\s]*([^\n]+)'],
            'project_number': [r'Project Number[:\s]*([^\n]+)', r'Project No[:\s]*([^\n]+)'],
            'country': [r'Country[:\s]*([^\n]+)'],
            'sector': [r'(?<!Sub)Sector[:\s]*([^\n]+)'],
            'subsector': [r'Subsector[:\s]*([^\n]+)', r'Sub-?sector[:\s]*([^\n]+)'],
            'consulting_type': [r'Consultant Type[:\s]*([^\n]+)'],
            'engagement_type': [r'Engagement Type[:\s]*([^\n]+)'],
            'selection_method': [r'Selection Method[:\s]*([^\n]+)'],
            'consultant_source': [r'Consultant Source[:\s]*([^\n]+)', r'Source[:\s]*(International|National|Regional)'],
            'budget_range': [r'Budget[:\s]*([^\n]+)', r'Estimated Cost[:\s]*([^\n]+)'],
            'duration': [r'Duration[:\s]*([^\n]+)'],
            'deadline': [r'Deadline[:\s]*([^\n]+)', r'Submission[:\s]*([^\n]+)'],
            'published_date': [r'Published[:\s]*([^\n]+)', r'Posted[:\s]*([^\n]+)'],
            'executing_agency': [r'Executing Agency[:\s]*([^\n]+)'],
            'implementing_agency': [r'Implementing Agency[:\s]*([^\n]+)'],
            'funding_source': [r'Funding[:\s]*([^\n]+)'],
        }
        
        for field, pattern_list in patterns.items():
            if not getattr(opp, field):
                for pattern in pattern_list:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        setattr(opp, field, match.group(1).strip()[:500])
                        break
        
        # Extract description
        self._extract_description_sections(opp, page_text, None)
    
    def _extract_description_sections(self, opp: ConsultingOpportunity, page_text: str, soup=None):
        """Extract description, objectives, scope, etc."""
        
        # Description patterns
        desc_patterns = [
            r'Description[:\s]*\n([^\n](?:.*?\n)*?)(?=\n[A-Z][a-z]+:|$)',
            r'Project Description[:\s]*\n(.*?)(?=\n[A-Z][a-z]+:|$)',
            r'Background[:\s]*\n(.*?)(?=\n[A-Z][a-z]+:|$)',
        ]
        
        for pattern in desc_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
            if match and not opp.description:
                opp.description = match.group(1).strip()[:3000]
                break
        
        # Objectives
        obj_match = re.search(r'Objectives?[:\s]*\n(.*?)(?=\n[A-Z][a-z]+:|$)', page_text, re.IGNORECASE | re.DOTALL)
        if obj_match:
            opp.objectives = obj_match.group(1).strip()[:2000]
        
        # Scope of Work
        scope_match = re.search(r'Scope of Work[:\s]*\n(.*?)(?=\n[A-Z][a-z]+:|$)', page_text, re.IGNORECASE | re.DOTALL)
        if scope_match:
            opp.scope_of_work = scope_match.group(1).strip()[:3000]
        
        # Deliverables
        deliv_match = re.search(r'Deliverables?[:\s]*\n(.*?)(?=\n[A-Z][a-z]+:|$)', page_text, re.IGNORECASE | re.DOTALL)
        if deliv_match:
            opp.deliverables = deliv_match.group(1).strip()[:2000]
        
        # Qualifications
        qual_match = re.search(r'Qualifications?[:\s]*\n(.*?)(?=\n[A-Z][a-z]+:|$)', page_text, re.IGNORECASE | re.DOTALL)
        if qual_match:
            opp.qualifications = qual_match.group(1).strip()[:2000]
        
        # If using BeautifulSoup, also try to find content divs
        if soup:
            for div in soup.find_all(['div', 'td'], class_=lambda x: x and ('content' in str(x).lower() or 'description' in str(x).lower())):
                text = div.get_text(strip=True)
                if len(text) > 100 and not opp.description:
                    opp.description = text[:3000]
                    break
    
    def _fetch_adb_project_details(self, opp: ConsultingOpportunity, project_url: str):
        """Fetch additional details from ADB project page"""
        try:
            self.driver.get(project_url)
            time.sleep(2)
            
            page_text = self.driver.find_element(By.TAG_NAME, 'body').text
            
            # Extract description if not already set
            if not opp.description:
                desc_match = re.search(r'Description\s*\n(.*?)(?=\n[A-Z][a-z]+\s*\n|$)', page_text, re.DOTALL)
                if desc_match:
                    opp.description = desc_match.group(1).strip()[:3000]
            
            # Extract other fields
            if not opp.sector:
                sector_match = re.search(r'Sector[:\s]*([^\n]+)', page_text)
                if sector_match:
                    opp.sector = sector_match.group(1).strip()
            
            if not opp.country:
                country_match = re.search(r'Country[:\s]*([^\n]+)', page_text)
                if country_match:
                    opp.country = country_match.group(1).strip()
            
            opp.project_page_url = project_url
            
        except Exception:
            pass
    
    def _go_to_next_page(self) -> bool:
        """Try to navigate to next page"""
        try:
            next_selectors = [
                "//a[contains(text(), 'Next')]",
                "//img[@title='Next']/parent::a",
                "//a[@title='Next']",
            ]
            
            for xpath in next_selectors:
                try:
                    next_btn = self.driver.find_element(By.XPATH, xpath)
                    if next_btn.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
                        time.sleep(0.5)
                        next_btn.click()
                        time.sleep(3)
                        return True
                except:
                    continue
            
            return False
            
        except Exception:
            return False
    
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
            
            self.opportunities = [ConsultingOpportunity(**item) for item in data]
            print(f"✓ Loaded {len(self.opportunities)} opportunities from {filename}")
            return self.opportunities
        except Exception as e:
            print(f"❌ Error loading JSON: {e}")
            return []
    
    def print_summary(self):
        """Print detailed summary of scraped opportunities"""
        if not self.opportunities:
            print("❌ No opportunities loaded")
            return
        
        print("\n" + "=" * 80)
        print(f"📊 CONSULTING OPPORTUNITIES SUMMARY: {len(self.opportunities)} total")
        print("=" * 80)
        
        # Statistics
        types = {}
        countries = {}
        sectors = {}
        with_description = 0
        
        for opp in self.opportunities:
            if opp.consulting_type:
                types[opp.consulting_type] = types.get(opp.consulting_type, 0) + 1
            if opp.country:
                countries[opp.country] = countries.get(opp.country, 0) + 1
            if opp.sector:
                sectors[opp.sector] = sectors.get(opp.sector, 0) + 1
            if opp.description:
                with_description += 1
        
        print(f"\n📝 Opportunities with full description: {with_description}/{len(self.opportunities)}")
        
        if types:
            print("\n📌 By Consulting Type:")
            for t, count in sorted(types.items(), key=lambda x: -x[1]):
                print(f"   • {t}: {count}")
        
        if countries:
            print("\n🌍 By Country (Top 15):")
            for country, count in sorted(countries.items(), key=lambda x: -x[1])[:15]:
                print(f"   • {country}: {count}")
        
        if sectors:
            print("\n🏢 By Sector (Top 10):")
            for sector, count in sorted(sectors.items(), key=lambda x: -x[1])[:10]:
                print(f"   • {sector}: {count}")
        
        print("\n" + "-" * 80)
        print("📋 Sample Opportunities (with details):")
        print("-" * 80)
        
        # Show samples with descriptions
        samples = [o for o in self.opportunities if o.description][:5]
        if not samples:
            samples = self.opportunities[:5]
        
        for i, opp in enumerate(samples):
            print(f"\n{'='*60}")
            print(f"[{i+1}] {opp.title[:70]}...")
            print(f"{'='*60}")
            print(f"  📋 Project Number: {opp.project_number or 'N/A'}")
            print(f"  🏷️  Type: {opp.consulting_type or 'N/A'}")
            print(f"  🌍 Country: {opp.country or 'N/A'}")
            print(f"  🏢 Sector: {opp.sector or 'N/A'}")
            print(f"  ⏰ Deadline: {opp.deadline or 'N/A'}")
            print(f"  💰 Budget: {opp.budget_range or 'N/A'}")
            print(f"  ⏱️  Duration: {opp.duration or 'N/A'}")
            print(f"  🔗 URL: {opp.detail_url[:60] if opp.detail_url else 'N/A'}...")
            
            if opp.description:
                print(f"\n  📝 Description:")
                print(f"     {opp.description[:300]}...")
            
            if opp.scope_of_work:
                print(f"\n  📋 Scope of Work:")
                print(f"     {opp.scope_of_work[:200]}...")


def main():
    """Main function to run the scraper"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║        ADB CONSULTING OPPORTUNITIES SCRAPER (CSRN) - FULL DETAILS           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Source: https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN...    ║
║                                                                              ║
║  Extracts FULL details including:                                            ║
║  • Project description, objectives, scope of work                            ║
║  • Qualifications, deliverables                                              ║
║  • Budget, duration, deadline                                                ║
║  • Country, sector, consulting type                                          ║
║  • Terms of reference links                                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize scraper
    scraper = ADBConsultingScraper(headless=True, delay=2.0)
    
    try:
        # Scrape opportunities WITH full details
        opportunities = scraper.scrape_opportunities(
            max_pages=5,        # Scrape 5 pages
            fetch_details=True  # Fetch FULL details for each opportunity
        )
        
        if opportunities:
            # Save results
            scraper.save_to_json("adb_consulting_opportunities.json")
            scraper.save_to_csv("adb_consulting_opportunities.csv")
            
            # Print summary
            scraper.print_summary()
        else:
            print("\n⚠ No opportunities were scraped.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
