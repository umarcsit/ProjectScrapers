"""
ADB (Asian Development Bank) Projects Scraper
Extracts project information from https://www.adb.org/projects
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class Project:
    """Data class to store project information"""
    project_id: str = ""
    title: str = ""
    country: str = ""
    sector: str = ""
    status: str = ""
    approval_date: str = ""
    signing_date: str = ""
    closing_date: str = ""
    financing_amount: str = ""
    borrower: str = ""
    executing_agency: str = ""
    description: str = ""
    project_url: str = ""


class ADBScraper:
    """Scraper for Asian Development Bank projects"""
    
    BASE_URL = "https://www.adb.org"
    PROJECTS_URL = "https://www.adb.org/projects"
    
    # ADB uses an API endpoint for project search
    API_URL = "https://www.adb.org/api/search/projects"
    
    def __init__(self, delay: float = 1.0):
        """
        Initialize the scraper
        
        Args:
            delay: Delay between requests in seconds (be respectful to the server)
        """
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })
        self.projects = []
    
    def _make_request(self, url: str, params: dict = None) -> Optional[requests.Response]:
        """Make a request with error handling and rate limiting"""
        try:
            time.sleep(self.delay)
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def get_projects_from_listing(self, page: int = 0, rows: int = 20) -> list:
        """
        Fetch projects from the ADB projects listing page
        
        Args:
            page: Page number (0-indexed)
            rows: Number of results per page
            
        Returns:
            List of project dictionaries
        """
        # ADB website uses a search/filter system
        # We'll scrape the main projects page with pagination
        params = {
            'page': page
        }
        
        url = f"{self.PROJECTS_URL}"
        response = self._make_request(url, params)
        
        if not response:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        projects = []
        
        # Find project items on the page
        # ADB uses different layouts, we'll try multiple selectors
        project_items = soup.select('.item-list .views-row, .view-content .views-row, .project-item, .search-result-item')
        
        if not project_items:
            # Try alternative selectors
            project_items = soup.select('[class*="project"], [class*="result"]')
        
        for item in project_items:
            project_data = self._parse_project_listing_item(item)
            if project_data:
                projects.append(project_data)
        
        return projects
    
    def _parse_project_listing_item(self, item) -> Optional[dict]:
        """Parse a project item from the listing page"""
        try:
            data = {}
            
            # Extract title and link
            title_elem = item.select_one('h3 a, h4 a, .title a, a.title, .views-field-title a')
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)
                data['project_url'] = self.BASE_URL + title_elem.get('href', '') if title_elem.get('href', '').startswith('/') else title_elem.get('href', '')
            
            # Extract project number/ID
            project_num = item.select_one('.project-number, .views-field-field-project-number, [class*="number"]')
            if project_num:
                data['project_id'] = project_num.get_text(strip=True)
            else:
                # Try to extract from URL
                if 'project_url' in data:
                    match = re.search(r'/projects/(\d+)', data.get('project_url', ''))
                    if match:
                        data['project_id'] = match.group(1)
            
            # Extract country
            country_elem = item.select_one('.country, .views-field-field-countries, [class*="country"]')
            if country_elem:
                data['country'] = country_elem.get_text(strip=True)
            
            # Extract sector
            sector_elem = item.select_one('.sector, .views-field-field-sector, [class*="sector"]')
            if sector_elem:
                data['sector'] = sector_elem.get_text(strip=True)
            
            # Extract status
            status_elem = item.select_one('.status, .views-field-field-status, [class*="status"]')
            if status_elem:
                data['status'] = status_elem.get_text(strip=True)
            
            # Extract date
            date_elem = item.select_one('.date, .views-field-field-date, [class*="date"]')
            if date_elem:
                data['approval_date'] = date_elem.get_text(strip=True)
            
            # Extract description/summary if available
            desc_elem = item.select_one('.description, .summary, .views-field-body, p')
            if desc_elem:
                data['description'] = desc_elem.get_text(strip=True)[:500]  # Limit length
            
            return data if data.get('title') or data.get('project_id') else None
            
        except Exception as e:
            print(f"Error parsing project item: {e}")
            return None
    
    def get_project_details(self, project_url: str) -> Optional[Project]:
        """
        Fetch detailed information for a specific project
        
        Args:
            project_url: URL of the project detail page
            
        Returns:
            Project object with all available details
        """
        response = self._make_request(project_url)
        if not response:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        project = Project(project_url=project_url)
        
        # Extract title
        title_elem = soup.select_one('h1, .page-title, .project-title')
        if title_elem:
            project.title = title_elem.get_text(strip=True)
        
        # Extract project ID
        project_id_elem = soup.select_one('.project-number, .field--name-field-project-number')
        if project_id_elem:
            project.project_id = project_id_elem.get_text(strip=True)
        else:
            # Try from URL
            match = re.search(r'/projects/(\d+)', project_url)
            if match:
                project.project_id = match.group(1)
        
        # Extract from detail fields - ADB uses various field structures
        field_mappings = {
            'country': ['.field--name-field-countries', '.country', '[class*="country"]'],
            'sector': ['.field--name-field-sector', '.sector', '[class*="sector"]'],
            'status': ['.field--name-field-status', '.status', '[class*="status"]'],
            'approval_date': ['.field--name-field-approval-date', '.approval-date', '[class*="approval"]'],
            'signing_date': ['.field--name-field-signing-date', '.signing-date', '[class*="signing"]'],
            'closing_date': ['.field--name-field-closing-date', '.closing-date', '[class*="closing"]'],
            'financing_amount': ['.field--name-field-financing', '.financing', '[class*="financing"], [class*="amount"]'],
            'borrower': ['.field--name-field-borrower', '.borrower', '[class*="borrower"]'],
            'executing_agency': ['.field--name-field-executing-agency', '.executing-agency', '[class*="executing"]'],
        }
        
        for field_name, selectors in field_mappings.items():
            for selector in selectors:
                elem = soup.select_one(selector)
                if elem:
                    value = elem.get_text(strip=True)
                    # Clean up label if present
                    value = re.sub(r'^[A-Za-z\s]+:\s*', '', value)
                    setattr(project, field_name, value)
                    break
        
        # Extract description
        desc_elem = soup.select_one('.field--name-body, .description, .project-description, article p')
        if desc_elem:
            project.description = desc_elem.get_text(strip=True)[:2000]
        
        # Try to extract from table format (ADB often uses tables)
        tables = soup.select('table')
        for table in tables:
            rows = table.select('tr')
            for row in rows:
                cells = row.select('td, th')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    
                    if 'project' in label and 'number' in label:
                        project.project_id = value
                    elif 'country' in label:
                        project.country = value
                    elif 'sector' in label:
                        project.sector = value
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
        
        return project
    
    def scrape_all_projects(self, max_pages: int = 10, fetch_details: bool = False) -> list:
        """
        Scrape all projects from multiple pages
        
        Args:
            max_pages: Maximum number of pages to scrape
            fetch_details: Whether to fetch detailed info for each project
            
        Returns:
            List of Project objects
        """
        all_projects = []
        
        print(f"Starting to scrape ADB projects (max {max_pages} pages)...")
        
        for page in range(max_pages):
            print(f"Scraping page {page + 1}...")
            projects = self.get_projects_from_listing(page=page)
            
            if not projects:
                print(f"No more projects found on page {page + 1}. Stopping.")
                break
            
            for proj_data in projects:
                if fetch_details and proj_data.get('project_url'):
                    print(f"  Fetching details for: {proj_data.get('title', 'Unknown')[:50]}...")
                    detailed = self.get_project_details(proj_data['project_url'])
                    if detailed:
                        all_projects.append(detailed)
                    else:
                        # Use basic data if details fetch fails
                        project = Project(**{k: v for k, v in proj_data.items() if hasattr(Project, k)})
                        all_projects.append(project)
                else:
                    project = Project(**{k: v for k, v in proj_data.items() if hasattr(Project, k)})
                    all_projects.append(project)
            
            print(f"  Found {len(projects)} projects on page {page + 1}")
        
        self.projects = all_projects
        print(f"\nTotal projects scraped: {len(all_projects)}")
        return all_projects
    
    def scrape_project_by_id(self, project_id: str) -> Optional[Project]:
        """
        Scrape a specific project by its ID
        
        Args:
            project_id: The ADB project number/ID
            
        Returns:
            Project object or None
        """
        url = f"{self.PROJECTS_URL}/{project_id}"
        return self.get_project_details(url)
    
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
    
    # Initialize scraper with 1.5 second delay between requests
    scraper = ADBScraper(delay=1.5)
    
    # Scrape projects (adjust max_pages as needed)
    # Set fetch_details=True to get full project information (slower)
    projects = scraper.scrape_all_projects(max_pages=5, fetch_details=True)
    
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
            print(f"Sector: {project.sector}")
            print(f"Status: {project.status}")
            print(f"Approval Date: {project.approval_date}")
            print(f"Financing: {project.financing_amount}")
            print(f"URL: {project.project_url}")
            if project.description:
                print(f"Description: {project.description[:200]}...")
    else:
        print("\nNo projects were scraped. The website structure may have changed.")
        print("Consider checking the website manually and updating the selectors.")


if __name__ == "__main__":
    main()
