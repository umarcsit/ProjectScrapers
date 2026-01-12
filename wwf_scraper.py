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
        # More comprehensive browser-like headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        })
        self.projects = []
    
    def fetch_page(self, url=None):
        """Fetch the webpage content."""
        target_url = url or self.BASE_URL
        try:
            # First visit the main site to get cookies
            self.session.get('https://wwf.org.pk/', timeout=30)
            time.sleep(1)
            
            response = self.session.get(target_url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {target_url}: {e}")
            return None
    
    def parse_consultancy_projects(self, html_content):
        """Parse HTML and extract individual consultancy projects."""
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        projects = []
        
        # The WWF page typically lists consultancies with numbered titles
        # Pattern: "XXX-Project Title" followed by submission details and links
        
        # Find all text content and parse it
        body_text = soup.get_text()
        
        # Look for patterns like "211-Financial Monitoring Expert..."
        # Each project has: Number-Title, submission info, deadline, TOR link, Application form link
        
        # Try to find project entries by looking for numbered patterns
        project_pattern = re.compile(
            r'(\d{1,3})\s*[-–]\s*(.+?)(?=Send your proposals|$)',
            re.DOTALL
        )
        
        # Find all links (for TOR and Application forms)
        all_links = {}
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            if href.endswith('.pdf') or 'terms' in text.lower() or 'application' in text.lower():
                all_links[text] = self._make_absolute_url(href)
        
        # Parse the main content looking for project blocks
        # Find all elements that might contain project info
        content_blocks = soup.find_all(['p', 'div', 'td', 'li'])
        
        current_project = None
        
        for block in content_blocks:
            text = block.get_text(strip=True)
            
            # Check if this starts a new project (numbered title)
            number_match = re.match(r'^(\d{1,3})\s*[-–]\s*(.+)', text)
            
            if number_match:
                # Save previous project
                if current_project and current_project.get('title'):
                    projects.append(current_project)
                
                # Start new project
                project_number = number_match.group(1)
                title_text = number_match.group(2)
                
                # Extract deadline if present in the text
                deadline_match = re.search(r'not\s*later\s*than\s*([\d-]+)', text, re.I)
                deadline = deadline_match.group(1) if deadline_match else None
                
                # Extract email addresses
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                
                current_project = {
                    'project_number': project_number,
                    'title': title_text.split('Send your')[0].strip() if 'Send your' in title_text else title_text,
                    'deadline': deadline,
                    'contact_emails': emails if emails else None,
                    'links': [],
                    'extracted_at': datetime.now().isoformat()
                }
                
                # Find associated links within this block
                for link in block.find_all('a', href=True):
                    link_text = link.get_text(strip=True)
                    link_url = self._make_absolute_url(link['href'])
                    current_project['links'].append({
                        'text': link_text,
                        'url': link_url
                    })
        
        # Don't forget the last project
        if current_project and current_project.get('title'):
            projects.append(current_project)
        
        # If we didn't find structured projects, try alternative parsing
        if not projects:
            projects = self._alternative_parse(soup)
        
        return projects
    
    def _alternative_parse(self, soup):
        """Alternative parsing method for different page structures."""
        projects = []
        
        # Look for any text blocks containing project-like information
        text_content = soup.get_text(separator='\n')
        
        # Split by project numbers
        lines = text_content.split('\n')
        current_project = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for project number pattern
            num_match = re.match(r'^(\d{1,3})\s*[-–]\s*(.+)', line)
            if num_match:
                if current_project.get('title'):
                    projects.append(current_project)
                
                current_project = {
                    'project_number': num_match.group(1),
                    'title': num_match.group(2).strip(),
                    'extracted_at': datetime.now().isoformat()
                }
            
            # Check for deadline
            elif 'not later than' in line.lower():
                date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', line)
                if date_match and current_project:
                    current_project['deadline'] = date_match.group(1)
            
            # Check for email
            elif '@' in line and current_project:
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', line)
                if emails:
                    current_project['contact_emails'] = emails
        
        if current_project.get('title'):
            projects.append(current_project)
        
        # Extract all PDF links
        pdf_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '.pdf' in href.lower():
                pdf_links.append({
                    'text': link.get_text(strip=True),
                    'url': self._make_absolute_url(href)
                })
        
        # If still no projects but we have PDF links, create entries from PDFs
        if not projects and pdf_links:
            for pdf in pdf_links:
                if 'terms' in pdf['text'].lower() or 'tor' in pdf['text'].lower():
                    projects.append({
                        'type': 'document',
                        'title': pdf['text'],
                        'document_url': pdf['url'],
                        'extracted_at': datetime.now().isoformat()
                    })
        
        return projects
    
    def _make_absolute_url(self, url):
        """Convert relative URL to absolute."""
        if not url:
            return url
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
            return None
        
        # Check if we got blocked
        if 'Not Acceptable' in html_content or len(html_content) < 1000:
            print("Warning: Page may have blocked the request or returned an error.")
            print(f"Response length: {len(html_content)} characters")
            print("Attempting with alternative method...")
            return self._scrape_with_alternative_method()
        
        print("Parsing page content...")
        self.projects = self.parse_consultancy_projects(html_content)
        
        soup = BeautifulSoup(html_content, 'html.parser')
        page_info = {
            'page_title': soup.title.string if soup.title else 'N/A',
            'url': self.BASE_URL,
            'scraped_at': datetime.now().isoformat(),
            'total_projects_found': len(self.projects)
        }
        
        print(f"Found {len(self.projects)} projects")
        
        return {
            'page_info': page_info,
            'projects': self.projects
        }
    
    def _scrape_with_alternative_method(self):
        """Try alternative scraping approach using curl-like request."""
        import subprocess
        
        try:
            # Use curl as fallback
            result = subprocess.run([
                'curl', '-s', '-L',
                '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                self.BASE_URL
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and result.stdout:
                html_content = result.stdout
                self.projects = self.parse_consultancy_projects(html_content)
                
                soup = BeautifulSoup(html_content, 'html.parser')
                return {
                    'page_info': {
                        'page_title': soup.title.string if soup.title else 'N/A',
                        'url': self.BASE_URL,
                        'scraped_at': datetime.now().isoformat(),
                        'total_projects_found': len(self.projects),
                        'method': 'curl_fallback'
                    },
                    'projects': self.projects
                }
        except Exception as e:
            print(f"Alternative method failed: {e}")
        
        return None
    
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
        
        # Flatten and prepare data for CSV
        flat_projects = []
        for project in projects:
            flat_project = {
                'project_number': project.get('project_number', ''),
                'title': project.get('title', ''),
                'deadline': project.get('deadline', ''),
                'contact_emails': ', '.join(project.get('contact_emails', [])) if project.get('contact_emails') else '',
                'document_url': project.get('document_url', ''),
                'extracted_at': project.get('extracted_at', '')
            }
            
            # Add links if present
            links = project.get('links', [])
            if links:
                tor_links = [l['url'] for l in links if 'term' in l.get('text', '').lower() or 'tor' in l.get('text', '').lower()]
                app_links = [l['url'] for l in links if 'application' in l.get('text', '').lower() or 'form' in l.get('text', '').lower()]
                flat_project['terms_of_reference_url'] = tor_links[0] if tor_links else ''
                flat_project['application_form_url'] = app_links[0] if app_links else ''
            
            flat_projects.append(flat_project)
        
        if flat_projects:
            fieldnames = ['project_number', 'title', 'deadline', 'contact_emails', 
                         'terms_of_reference_url', 'application_form_url', 'document_url', 'extracted_at']
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(flat_projects)
            
            print(f"Data saved to {filename}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("WWF Pakistan Consultancy Projects Scraper")
    print("=" * 70)
    
    scraper = WWFScraper()
    data = scraper.scrape()
    
    if data:
        # Save to both JSON and CSV
        scraper.save_to_json(data)
        scraper.save_to_csv(data)
        
        # Print summary
        print("\n" + "=" * 70)
        print("EXTRACTION SUMMARY")
        print("=" * 70)
        print(f"Page Title: {data['page_info']['page_title']}")
        print(f"URL: {data['page_info']['url']}")
        print(f"Total Projects Found: {data['page_info']['total_projects_found']}")
        print(f"Scraped At: {data['page_info']['scraped_at']}")
        
        if data['projects']:
            print("\n" + "-" * 70)
            print("CONSULTANCY PROJECTS:")
            print("-" * 70)
            for i, project in enumerate(data['projects'][:20], 1):  # Show first 20
                num = project.get('project_number', 'N/A')
                title = project.get('title', 'No Title')[:80]
                deadline = project.get('deadline', 'N/A')
                print(f"\n[{num}] {title}")
                if deadline and deadline != 'N/A':
                    print(f"     Deadline: {deadline}")
                if project.get('contact_emails'):
                    print(f"     Contact: {', '.join(project['contact_emails'])}")
                if project.get('links'):
                    print(f"     Documents: {len(project['links'])} link(s)")
            
            if len(data['projects']) > 20:
                print(f"\n... and {len(data['projects']) - 20} more projects")
                print("See the JSON/CSV files for complete data.")
    else:
        print("No data extracted. The website may be blocking automated requests.")
        print("Try accessing the page manually or using a VPN.")
    
    return data


if __name__ == "__main__":
    main()
