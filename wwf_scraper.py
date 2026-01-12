"""
WWF Pakistan Consultancy Projects Scraper
Extracts project information from https://wwf.org.pk/consultancy/
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
from datetime import datetime
import re
import time


class WWFScraper:
    """Scraper for WWF Pakistan consultancy projects."""
    
    BASE_URL = "https://wwf.org.pk/consultancy/"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.projects = []
    
    def fetch_page(self, url=None):
        """Fetch the webpage content."""
        target_url = url or self.BASE_URL
        try:
            response = self.session.get(target_url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {target_url}: {e}")
            return None
    
    def parse_projects(self, html_content):
        """Parse HTML and extract project information."""
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        projects = []
        
        # Try multiple selectors to find project listings
        # Common patterns for consultancy/tender pages
        selectors = [
            'article',
            '.post',
            '.consultancy-item',
            '.tender-item',
            '.project-item',
            '.entry',
            '.listing-item',
            'table tr',
            '.card',
            '.job-listing',
            '.opportunity',
            'div[class*="consult"]',
            'div[class*="tender"]',
            'div[class*="project"]',
        ]
        
        items = []
        for selector in selectors:
            found = soup.select(selector)
            if found:
                items = found
                print(f"Found {len(found)} items using selector: {selector}")
                break
        
        # If no specific items found, try to extract from the main content
        if not items:
            # Look for the main content area
            main_content = soup.find('main') or soup.find('div', class_='content') or soup.find('div', id='content')
            if main_content:
                items = [main_content]
            else:
                items = [soup.body] if soup.body else [soup]
        
        # Extract project details
        for item in items:
            project = self._extract_project_details(item)
            if project and project.get('title'):
                projects.append(project)
        
        # Also try to find downloadable documents (PDFs, DOCs)
        documents = self._extract_documents(soup)
        if documents:
            for doc in documents:
                projects.append({
                    'type': 'document',
                    'title': doc.get('text', 'Document'),
                    'url': doc.get('url'),
                    'extracted_at': datetime.now().isoformat()
                })
        
        return projects
    
    def _extract_project_details(self, element):
        """Extract details from a single project element."""
        project = {}
        
        # Extract title
        title_elem = (
            element.find(['h1', 'h2', 'h3', 'h4', 'h5']) or
            element.find(class_=re.compile(r'title|heading', re.I)) or
            element.find('a')
        )
        if title_elem:
            project['title'] = title_elem.get_text(strip=True)
            if title_elem.name == 'a' and title_elem.get('href'):
                project['link'] = self._make_absolute_url(title_elem['href'])
        
        # Extract description/content
        desc_elem = (
            element.find(class_=re.compile(r'desc|content|excerpt|summary', re.I)) or
            element.find('p')
        )
        if desc_elem:
            project['description'] = desc_elem.get_text(strip=True)
        
        # Extract date
        date_elem = (
            element.find('time') or
            element.find(class_=re.compile(r'date|posted|published', re.I))
        )
        if date_elem:
            project['date'] = date_elem.get_text(strip=True)
            if date_elem.get('datetime'):
                project['datetime'] = date_elem['datetime']
        
        # Extract deadline if present
        deadline_elem = element.find(string=re.compile(r'deadline|closing|last date', re.I))
        if deadline_elem:
            parent = deadline_elem.parent
            if parent:
                project['deadline'] = parent.get_text(strip=True)
        
        # Extract location
        location_elem = element.find(class_=re.compile(r'location|place', re.I))
        if location_elem:
            project['location'] = location_elem.get_text(strip=True)
        
        # Extract any links within the item
        links = element.find_all('a', href=True)
        project_links = []
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)
            if href and not href.startswith('#'):
                project_links.append({
                    'text': text,
                    'url': self._make_absolute_url(href)
                })
        if project_links:
            project['links'] = project_links
        
        # Extract all text content as fallback
        if not project.get('description'):
            all_text = element.get_text(separator=' ', strip=True)
            if all_text and len(all_text) > 20:
                project['full_text'] = all_text[:1000]  # Limit to 1000 chars
        
        project['extracted_at'] = datetime.now().isoformat()
        
        return project
    
    def _extract_documents(self, soup):
        """Extract links to downloadable documents."""
        documents = []
        doc_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx']
        
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            if any(ext in href for ext in doc_extensions):
                documents.append({
                    'text': link.get_text(strip=True),
                    'url': self._make_absolute_url(link['href'])
                })
        
        return documents
    
    def _make_absolute_url(self, url):
        """Convert relative URL to absolute."""
        if url.startswith('http'):
            return url
        elif url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            return 'https://wwf.org.pk' + url
        else:
            return self.BASE_URL + url
    
    def scrape(self):
        """Main scraping method."""
        print(f"Fetching page: {self.BASE_URL}")
        html_content = self.fetch_page()
        
        if not html_content:
            print("Failed to fetch the page.")
            return []
        
        print("Parsing page content...")
        self.projects = self.parse_projects(html_content)
        
        # Also extract general page information
        soup = BeautifulSoup(html_content, 'html.parser')
        page_info = {
            'page_title': soup.title.string if soup.title else 'N/A',
            'url': self.BASE_URL,
            'scraped_at': datetime.now().isoformat(),
            'total_items_found': len(self.projects)
        }
        
        print(f"Found {len(self.projects)} items")
        
        return {
            'page_info': page_info,
            'projects': self.projects,
            'raw_html_preview': html_content[:5000] if html_content else None  # For debugging
        }
    
    def save_to_json(self, data, filename='wwf_consultancy_projects.json'):
        """Save extracted data to JSON file."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {filename}")
    
    def save_to_csv(self, data, filename='wwf_consultancy_projects.csv'):
        """Save extracted data to CSV file."""
        projects = data.get('projects', [])
        if not projects:
            print("No projects to save to CSV")
            return
        
        # Get all unique keys from all projects
        all_keys = set()
        for project in projects:
            all_keys.update(project.keys())
        
        # Remove complex nested fields for CSV
        simple_keys = [k for k in all_keys if k not in ['links']]
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(simple_keys))
            writer.writeheader()
            for project in projects:
                # Flatten the project data for CSV
                row = {k: v for k, v in project.items() if k in simple_keys}
                writer.writerow(row)
        
        print(f"Data saved to {filename}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("WWF Pakistan Consultancy Projects Scraper")
    print("=" * 60)
    
    scraper = WWFScraper()
    data = scraper.scrape()
    
    if data:
        # Save to both JSON and CSV
        scraper.save_to_json(data)
        scraper.save_to_csv(data)
        
        # Print summary
        print("\n" + "=" * 60)
        print("EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"Page Title: {data['page_info']['page_title']}")
        print(f"URL: {data['page_info']['url']}")
        print(f"Total Items Found: {data['page_info']['total_items_found']}")
        print(f"Scraped At: {data['page_info']['scraped_at']}")
        
        if data['projects']:
            print("\n" + "-" * 60)
            print("EXTRACTED PROJECTS/ITEMS:")
            print("-" * 60)
            for i, project in enumerate(data['projects'], 1):
                print(f"\n[{i}] {project.get('title', 'No Title')}")
                if project.get('description'):
                    print(f"    Description: {project['description'][:200]}...")
                if project.get('date'):
                    print(f"    Date: {project['date']}")
                if project.get('deadline'):
                    print(f"    Deadline: {project['deadline']}")
                if project.get('link'):
                    print(f"    Link: {project['link']}")
                if project.get('links'):
                    print(f"    Associated Links: {len(project['links'])}")
    else:
        print("No data extracted.")
    
    return data


if __name__ == "__main__":
    main()
