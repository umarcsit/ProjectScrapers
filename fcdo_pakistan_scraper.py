#!/usr/bin/env python3
"""
FCDO Development Tracker Scraper for Pakistan Projects
Scrapes project information from https://devtracker.fcdo.gov.uk/countries/PK/projects
Extracts detailed description and objective from each project's detail page.
"""

import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import quote
from datetime import datetime
import sys
import concurrent.futures
from threading import Lock


class FCDOPakistanScraper:
    """Scraper for FCDO Development Tracker Pakistan projects."""
    
    # API endpoint for IATI data
    API_BASE_URL = "https://fcdo2.iati.cloud/api/v2/activity/"
    
    # DevTracker base URL for detail pages
    DEVTRACKER_BASE_URL = "https://devtracker.fcdo.gov.uk"
    
    # UK Government organization references to filter
    UK_GOV_ORGS = [
        "GB-GOV-1",      # Foreign, Commonwealth and Development Office (FCDO)
        "GB-GOV-7",      # Department for Environment, Food and Rural Affairs
        "GB-GOV-13",     # Department for Business, Energy and Industrial Strategy
        "GB-GOV-26",     # Department of Science, Innovation and Technology
        "gb-coh-03877777"  # British International Investment
    ]
    
    # Activity status mapping
    ACTIVITY_STATUS = {
        "1": "Pipeline/identification",
        "2": "Implementation",
        "3": "Finalisation",
        "4": "Closed",
        "5": "Cancelled",
        "6": "Suspended"
    }
    
    def __init__(self, include_closed=True, page_size=100):
        """
        Initialize the scraper.
        
        Args:
            include_closed: If True, include closed projects. If False, only active.
            page_size: Number of results per API request.
        """
        self.include_closed = include_closed
        self.page_size = page_size
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.print_lock = Lock()
    
    def _build_api_query(self, start=0):
        """Build the API query parameters."""
        # Base query for Pakistan
        params = {
            'q': 'recipient_country_code:(PK)',
            'fq': f'reporting_org_ref:({" OR ".join(self.UK_GOV_ORGS)})',
            'fl': '*',  # Get all fields
            'rows': self.page_size,
            'start': start,
            'sort': 'activity_date_start_actual desc'
        }
        
        # Filter by activity status if not including closed
        if not self.include_closed:
            params['fq'] = params['fq'] + ' AND activity_status_code:(2)'
        
        return params
    
    def fetch_projects_from_api(self):
        """Fetch all projects from the IATI API."""
        all_projects = []
        start = 0
        total_found = None
        
        print("Fetching projects from IATI API...")
        
        while True:
            params = self._build_api_query(start)
            
            try:
                response = self.session.get(self.API_BASE_URL, params=params, timeout=60)
                response.raise_for_status()
                data = response.json()
                
                if total_found is None:
                    total_found = data['response']['numFound']
                    print(f"Total projects found: {total_found}")
                
                docs = data['response']['docs']
                if not docs:
                    break
                
                all_projects.extend(docs)
                print(f"Fetched {len(all_projects)}/{total_found} projects...")
                
                start += self.page_size
                
                if start >= total_found:
                    break
                    
                # Small delay to be respectful to the API
                time.sleep(0.3)
                
            except requests.RequestException as e:
                print(f"Error fetching from API: {e}")
                break
        
        print(f"Total projects fetched: {len(all_projects)}")
        return all_projects
    
    def scrape_detail_page(self, iati_identifier):
        """
        Scrape the detail page for a project to get Description and Objective.
        
        Args:
            iati_identifier: The IATI identifier for the project.
            
        Returns:
            dict with 'description' and 'objective' keys.
        """
        encoded_id = quote(iati_identifier, safe='')
        url = f"{self.DEVTRACKER_BASE_URL}/projects/{encoded_id}/summary"
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            description = ""
            objective = ""
            
            # Find Description section
            desc_heading = soup.find('h2', string=re.compile(r'Description', re.IGNORECASE))
            if desc_heading:
                # Get the next paragraph(s) after the description heading
                desc_content = []
                for sibling in desc_heading.find_next_siblings():
                    if sibling.name == 'p':
                        desc_content.append(sibling.get_text(strip=True))
                    elif sibling.name == 'hr' or (sibling.name and 'heading' in str(sibling.get('class', []))):
                        break
                description = ' '.join(desc_content)
            
            # Find Objectives section (might be in different formats)
            obj_heading = soup.find(['h2', 'h3'], string=re.compile(r'Objective', re.IGNORECASE))
            if obj_heading:
                obj_content = []
                for sibling in obj_heading.find_next_siblings():
                    if sibling.name == 'p':
                        obj_content.append(sibling.get_text(strip=True))
                    elif sibling.name == 'hr' or (sibling.name and 'heading' in str(sibling.get('class', []))):
                        break
                objective = ' '.join(obj_content)
            
            # Also check for policy marker objectives
            policy_markers = soup.find_all('div', class_='app-policy-marker')
            if policy_markers:
                policy_objectives = []
                for marker in policy_markers:
                    title = marker.find('span', class_='app-policy-marker--title')
                    significance = marker.find('strong', class_='app-policy-marker--significance')
                    if title and significance:
                        policy_objectives.append(f"{title.get_text(strip=True)}: {significance.get_text(strip=True)}")
                if policy_objectives and not objective:
                    objective = "; ".join(policy_objectives)
            
            return {
                'description': description,
                'objective': objective
            }
            
        except Exception as e:
            return {'description': '', 'objective': ''}
    
    def scrape_detail_page_with_index(self, args):
        """Wrapper for parallel scraping with index tracking."""
        index, total, iati_identifier = args
        result = self.scrape_detail_page(iati_identifier)
        with self.print_lock:
            print(f"[{index}/{total}] Scraped detail page: {iati_identifier[:50]}...")
        return iati_identifier, result
    
    def parse_date(self, date_str):
        """Parse date string from API into a standard format."""
        if not date_str:
            return ""
        
        try:
            # Handle ISO format
            if 'T' in str(date_str):
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
            # Handle string format like "Mon Dec 19 00:00:00 UTC 2016"
            if isinstance(date_str, str) and 'UTC' in date_str:
                dt = datetime.strptime(date_str, '%a %b %d %H:%M:%S UTC %Y')
                return dt.strftime('%Y-%m-%d')
            return str(date_str)[:10]
        except:
            return str(date_str) if date_str else ""
    
    def extract_project_data(self, project, detail_info=None):
        """
        Extract and clean project data from API response.
        
        Args:
            project: Raw project data from API.
            detail_info: Optional detail info from scraping detail page.
            
        Returns:
            dict with cleaned project data.
        """
        # Helper function to get first value from list or string
        def get_first(val):
            if isinstance(val, list) and val:
                return val[0]
            return val if val else ""
        
        # Helper function to join list values
        def join_list(val, sep="; "):
            if isinstance(val, list):
                return sep.join(str(v) for v in val if v)
            return str(val) if val else ""
        
        # Parse dates
        start_dates = project.get('activity_date_iso_date', [])
        start_date = ""
        end_date = ""
        
        date_types = project.get('activity_date_type', [])
        if isinstance(start_dates, list) and isinstance(date_types, list):
            for i, dtype in enumerate(date_types):
                if i < len(start_dates):
                    if dtype in ['1', '2']:  # Planned or Actual start
                        start_date = self.parse_date(start_dates[i])
                    elif dtype in ['3', '4']:  # Planned or Actual end
                        end_date = self.parse_date(start_dates[i])
        
        # If no end date found, try activity_date_end_actual
        if not end_date:
            end_date = self.parse_date(project.get('activity_date_end_actual', ''))
        if not start_date:
            start_date = self.parse_date(project.get('activity_date_start_actual', ''))
        
        # Get budget information
        budget_values = project.get('budget_value', [])
        total_budget = sum(budget_values) if isinstance(budget_values, list) else (budget_values or 0)
        
        # Get description from API
        api_description = get_first(project.get('description_narrative', ''))
        
        # Combine API description with detail page description and objective
        combined_description = api_description
        if detail_info:
            detail_desc = detail_info.get('description', '')
            detail_obj = detail_info.get('objective', '')
            
            # If detail description is different and more detailed, use it
            if detail_desc and detail_desc != api_description:
                if len(detail_desc) > len(api_description):
                    combined_description = detail_desc
            
            # Append objective if available
            if detail_obj:
                combined_description = f"{combined_description}\n\nObjectives: {detail_obj}"
        
        # Activity status
        status_code = project.get('activity_status_code', '')
        status_name = self.ACTIVITY_STATUS.get(str(status_code), status_code)
        
        return {
            'IATI_Identifier': project.get('iati_identifier', ''),
            'Title': get_first(project.get('title_narrative', '')),
            'Description': combined_description,
            'Reporting_Organization': get_first(project.get('reporting_org_narrative', '')),
            'Reporting_Org_Ref': project.get('reporting_org_ref', ''),
            'Reporting_Org_Type': project.get('reporting_org_type_code', ''),
            'Activity_Status': status_name,
            'Activity_Status_Code': status_code,
            'Start_Date': start_date,
            'End_Date': end_date,
            'Total_Budget': total_budget,
            'Default_Currency': project.get('default_currency', 'GBP'),
            'Recipient_Country': join_list(project.get('recipient_country_code', [])),
            'Recipient_Country_Percentage': join_list(project.get('recipient_country_percentage', [])),
            'Recipient_Region': join_list(project.get('recipient_region_code', [])),
            'Sectors': join_list(project.get('sector_narrative', [])),
            'Sector_Codes': join_list(project.get('sector_code', [])),
            'Participating_Organizations': join_list(project.get('participating_org_narrative', [])),
            'Participating_Org_Refs': join_list(project.get('participating_org_ref', [])),
            'Participating_Org_Roles': join_list(project.get('participating_org_role', [])),
            'Locations': join_list(project.get('location_name_narrative', [])),
            'Contact_Email': get_first(project.get('contact_info_email', '')),
            'Contact_Telephone': get_first(project.get('contact_info_telephone', '')),
            'Contact_Organization': get_first(project.get('contact_info_organisation_narrative', '')),
            'Contact_Address': get_first(project.get('contact_info_mailing_address_narrative', '')),
            'Document_Links': join_list(project.get('document_link_url', [])),
            'Document_Categories': join_list(project.get('document_link_category_code', [])),
            'Policy_Markers': join_list(project.get('policy_marker_code', [])),
            'Collaboration_Type': project.get('collaboration_type_code', ''),
            'Default_Flow_Type': project.get('default_flow_type_code', ''),
            'Default_Finance_Type': project.get('default_finance_type_code', ''),
            'Default_Aid_Type': get_first(project.get('default_aid_type_code', '')),
            'Default_Tied_Status': project.get('default_tied_status_code', ''),
            'Activity_Scope': project.get('activity_scope_code', ''),
            'Hierarchy': project.get('hierarchy', ''),
            'Language': project.get('lang', ''),
            'Project_URL': f"{self.DEVTRACKER_BASE_URL}/projects/{quote(project.get('iati_identifier', ''), safe='')}/summary"
        }
    
    def scrape_all(self, scrape_details=True, max_workers=10):
        """
        Main method to scrape all Pakistan projects.
        
        Args:
            scrape_details: If True, also scrape detail pages for each project.
            max_workers: Number of parallel workers for detail page scraping.
            
        Returns:
            pandas DataFrame with all project data.
        """
        # Fetch all projects from API
        projects = self.fetch_projects_from_api()
        
        if not projects:
            print("No projects found!")
            return pd.DataFrame()
        
        total = len(projects)
        print(f"\nProcessing {total} projects...")
        
        # Scrape detail pages in parallel if requested
        detail_info_map = {}
        if scrape_details:
            print(f"\nScraping detail pages with {max_workers} parallel workers...")
            args_list = [(i+1, total, p.get('iati_identifier', '')) for i, p in enumerate(projects)]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(self.scrape_detail_page_with_index, args_list))
                for iati_id, detail_info in results:
                    detail_info_map[iati_id] = detail_info
        
        # Extract data from all projects
        all_data = []
        for project in projects:
            iati_id = project.get('iati_identifier', '')
            detail_info = detail_info_map.get(iati_id)
            project_data = self.extract_project_data(project, detail_info)
            all_data.append(project_data)
        
        df = pd.DataFrame(all_data)
        print(f"\nTotal projects processed: {len(df)}")
        
        return df
    
    def save_to_csv(self, df, filename='fcdo_pakistan_projects.csv'):
        """Save DataFrame to CSV file."""
        if df.empty:
            print("No data to save!")
            return
        
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"Data saved to: {filename}")
        print(f"Total rows: {len(df)}")
        print(f"Total columns: {len(df.columns)}")


def main():
    """Main entry point for the scraper."""
    print("=" * 60)
    print("FCDO Pakistan Projects Scraper")
    print("Source: https://devtracker.fcdo.gov.uk/countries/PK/projects")
    print("=" * 60)
    print()
    
    # Initialize scraper with both active and closed projects
    scraper = FCDOPakistanScraper(include_closed=True, page_size=100)
    
    # Scrape all projects (including detail pages with parallel processing)
    df = scraper.scrape_all(scrape_details=True, max_workers=15)
    
    # Save to CSV
    if not df.empty:
        output_file = 'fcdo_pakistan_projects.csv'
        scraper.save_to_csv(df, output_file)
        
        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total projects scraped: {len(df)}")
        print(f"Columns in CSV: {list(df.columns)}")
        
        # Status breakdown
        if 'Activity_Status' in df.columns:
            print("\nActivity Status Breakdown:")
            print(df['Activity_Status'].value_counts().to_string())
        
        # Organization breakdown
        if 'Reporting_Organization' in df.columns:
            print("\nReporting Organization Breakdown:")
            print(df['Reporting_Organization'].value_counts().to_string())
    else:
        print("No data was collected. Please check the errors above.")
    
    return df


if __name__ == "__main__":
    main()
