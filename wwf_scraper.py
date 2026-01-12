#!/usr/bin/env python3
"""
WWF Pakistan Consultancy Projects Scraper
Extracts project information from https://wwf.org.pk/consultancy/
and saves it to a CSV file.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import csv
import re
from datetime import datetime


def fetch_page(url):
    """Fetch the webpage content."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching the page: {e}")
        return None


def clean_text(text):
    """Clean and normalize text."""
    if text:
        # Remove extra whitespace and newlines
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    return ""


def extract_projects(html_content):
    """Extract project information from the HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    projects = []
    
    # Try different common patterns for listing content
    # Look for article elements, divs with specific classes, tables, etc.
    
    # Pattern 1: Look for common content containers
    content_areas = soup.find_all(['article', 'div', 'section'], 
                                   class_=re.compile(r'(post|entry|content|consultanc|project|item|card)', re.I))
    
    # Pattern 2: Look for tables (often used for listings)
    tables = soup.find_all('table')
    
    # Pattern 3: Look for list items
    list_items = soup.find_all('li', class_=re.compile(r'(post|entry|item)', re.I))
    
    # Pattern 4: Look for headings followed by content
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])
    
    # Try to extract from tables first (common for consultancy listings)
    for table in tables:
        rows = table.find_all('tr')
        for row in rows[1:]:  # Skip header row
            cells = row.find_all(['td', 'th'])
            if cells:
                project = {}
                for i, cell in enumerate(cells):
                    # Try to get header names
                    header_row = rows[0] if rows else None
                    header_cells = header_row.find_all(['td', 'th']) if header_row else []
                    header_name = clean_text(header_cells[i].get_text()) if i < len(header_cells) else f"Column_{i+1}"
                    project[header_name] = clean_text(cell.get_text())
                    
                    # Check for links
                    link = cell.find('a')
                    if link and link.get('href'):
                        project[f"{header_name}_Link"] = link.get('href')
                
                if project:
                    projects.append(project)
    
    # If no table data, try content areas
    if not projects:
        for area in content_areas:
            project = {}
            
            # Extract title
            title = area.find(['h1', 'h2', 'h3', 'h4', 'h5', 'a'])
            if title:
                project['Title'] = clean_text(title.get_text())
                if title.name == 'a' and title.get('href'):
                    project['Link'] = title.get('href')
            
            # Extract description/content
            desc = area.find(['p', 'div'], class_=re.compile(r'(desc|content|excerpt|summary)', re.I))
            if desc:
                project['Description'] = clean_text(desc.get_text())
            
            # Extract date if available
            date = area.find(['time', 'span', 'div'], class_=re.compile(r'(date|time|posted)', re.I))
            if date:
                project['Date'] = clean_text(date.get_text())
            
            # Extract any links
            links = area.find_all('a')
            for link in links:
                href = link.get('href')
                if href and 'pdf' in href.lower():
                    project['PDF_Link'] = href
                elif href and href.startswith('http'):
                    if 'Link' not in project:
                        project['Link'] = href
            
            if project and len(project) > 0:
                projects.append(project)
    
    # If still no projects found, extract all text content with structure
    if not projects:
        # Get main content area
        main_content = soup.find(['main', 'div'], class_=re.compile(r'(content|main|entry)', re.I))
        if not main_content:
            main_content = soup.find('body')
        
        if main_content:
            # Extract all paragraphs and headings
            elements = main_content.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'a'])
            current_project = {}
            
            for elem in elements:
                text = clean_text(elem.get_text())
                if not text:
                    continue
                    
                if elem.name in ['h1', 'h2', 'h3', 'h4']:
                    if current_project:
                        projects.append(current_project)
                    current_project = {'Title': text}
                    if elem.find('a'):
                        link = elem.find('a')
                        if link.get('href'):
                            current_project['Link'] = link.get('href')
                elif elem.name == 'a' and elem.get('href'):
                    href = elem.get('href')
                    if 'pdf' in href.lower():
                        current_project['PDF_Link'] = href
                        current_project['PDF_Title'] = text
                    else:
                        if 'Title' not in current_project:
                            current_project['Title'] = text
                        current_project['Link'] = href
                elif elem.name == 'p' and current_project:
                    if 'Description' in current_project:
                        current_project['Description'] += ' ' + text
                    else:
                        current_project['Description'] = text
            
            if current_project:
                projects.append(current_project)
    
    return projects


def extract_all_links_and_content(html_content, base_url):
    """Extract all meaningful content and links from the page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    projects = []
    
    # Find all links that might be consultancy/project related
    all_links = soup.find_all('a')
    
    for link in all_links:
        href = link.get('href', '')
        text = clean_text(link.get_text())
        
        # Skip empty or navigation links
        if not text or len(text) < 5:
            continue
        if href in ['#', '', '/'] or 'javascript:' in href:
            continue
        
        # Make absolute URL
        if href and not href.startswith('http'):
            if href.startswith('/'):
                href = base_url.rstrip('/') + href
            else:
                href = base_url.rstrip('/') + '/' + href
        
        # Look for context around the link
        parent = link.find_parent(['li', 'div', 'td', 'article', 'section'])
        description = ""
        date = ""
        
        if parent:
            # Get all text from parent, excluding the link text
            parent_text = clean_text(parent.get_text())
            if parent_text != text:
                description = parent_text
            
            # Look for date patterns
            date_match = re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}', parent_text, re.I)
            if date_match:
                date = date_match.group()
        
        project = {
            'Title': text,
            'Link': href,
            'Description': description if description != text else "",
            'Date': date
        }
        
        # Avoid duplicates
        if not any(p.get('Title') == text and p.get('Link') == href for p in projects):
            projects.append(project)
    
    return projects


def save_to_csv(projects, filename='wwf_consultancy_projects.csv'):
    """Save the extracted projects to a CSV file."""
    if not projects:
        print("No projects to save.")
        return False
    
    # Get all unique keys
    all_keys = set()
    for project in projects:
        all_keys.update(project.keys())
    
    # Define preferred column order
    preferred_order = ['Title', 'Description', 'Date', 'Link', 'PDF_Link', 'PDF_Title']
    columns = [col for col in preferred_order if col in all_keys]
    columns.extend([col for col in sorted(all_keys) if col not in columns])
    
    # Create DataFrame and save
    df = pd.DataFrame(projects)
    df = df.reindex(columns=columns)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    
    print(f"Successfully saved {len(projects)} projects to {filename}")
    return True


def main():
    """Main function to scrape WWF consultancy page."""
    url = "https://wwf.org.pk/consultancy/"
    base_url = "https://wwf.org.pk"
    
    print(f"Fetching data from: {url}")
    print("-" * 50)
    
    html_content = fetch_page(url)
    
    if not html_content:
        print("Failed to fetch the page. Please check the URL and your internet connection.")
        return
    
    # Try primary extraction method
    projects = extract_projects(html_content)
    
    # If no projects found, try alternative method
    if not projects:
        print("Trying alternative extraction method...")
        projects = extract_all_links_and_content(html_content, base_url)
    
    # Filter out non-relevant entries
    filtered_projects = []
    for p in projects:
        title = p.get('Title', '').lower()
        # Skip common navigation/footer items
        skip_terms = ['home', 'about', 'contact', 'facebook', 'twitter', 'instagram', 
                      'linkedin', 'menu', 'search', 'login', 'subscribe', 'copyright']
        if not any(term == title for term in skip_terms):
            filtered_projects.append(p)
    
    if filtered_projects:
        projects = filtered_projects
    
    print(f"Found {len(projects)} projects/entries")
    
    # Save to CSV
    output_file = 'wwf_consultancy_projects.csv'
    save_to_csv(projects, output_file)
    
    # Print summary
    print("\n" + "=" * 50)
    print("EXTRACTION SUMMARY")
    print("=" * 50)
    print(f"Total entries extracted: {len(projects)}")
    print(f"Output file: {output_file}")
    print(f"Extraction date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Show first few entries
    if projects:
        print("\nFirst few entries:")
        for i, project in enumerate(projects[:5], 1):
            print(f"\n{i}. {project.get('Title', 'N/A')[:60]}...")
            if project.get('Link'):
                print(f"   Link: {project.get('Link')[:60]}...")


if __name__ == "__main__":
    main()
