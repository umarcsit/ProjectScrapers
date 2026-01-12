#!/usr/bin/env python3
"""
IsDB Tenders Scraper
Scrapes project tender information from https://www.isdb.org/project-procurement/tenders
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime

# Base URL
BASE_URL = "https://www.isdb.org"
TENDERS_URL = f"{BASE_URL}/project-procurement/tenders"

# Headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}


def get_page_content(url, retries=3):
    """Fetch page content with retries"""
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    return None


def get_all_tender_pages():
    """Get all pagination pages from the tenders listing"""
    pages = [TENDERS_URL]
    content = get_page_content(TENDERS_URL)
    
    if not content:
        return pages
    
    soup = BeautifulSoup(content, 'lxml')
    
    # Find pagination links
    pagination = soup.find('ul', class_='pagination')
    if pagination:
        page_links = pagination.find_all('a', href=True)
        for link in page_links:
            href = link['href']
            if href not in pages and 'page=' in href:
                if href.startswith('/'):
                    href = BASE_URL + href
                elif not href.startswith('http'):
                    href = TENDERS_URL + '?' + href.split('?')[-1]
                pages.append(href)
    
    return list(set(pages))


def extract_project_urls_from_listing(content):
    """Extract project URLs from a listing page"""
    soup = BeautifulSoup(content, 'lxml')
    project_urls = []
    
    # Look for project links in various possible containers
    # Try different selectors that might contain tender/project links
    selectors = [
        'a[href*="/project"]',
        'a[href*="/tender"]',
        'a[href*="/procurement"]',
        '.tender-item a',
        '.project-item a',
        '.card a',
        'table a',
        '.view-content a',
        'article a',
    ]
    
    for selector in selectors:
        links = soup.select(selector)
        for link in links:
            href = link.get('href', '')
            if href and '/project' in href.lower() or '/tender' in href.lower():
                if href.startswith('/'):
                    href = BASE_URL + href
                elif not href.startswith('http'):
                    href = BASE_URL + '/' + href
                if href not in project_urls and 'isdb.org' in href:
                    project_urls.append(href)
    
    # Also look for any links that might be project-related
    all_links = soup.find_all('a', href=True)
    for link in all_links:
        href = link['href']
        text = link.get_text(strip=True).lower()
        # Check if it looks like a project link
        if any(keyword in href.lower() for keyword in ['project', 'tender', 'procurement', 'bid']):
            if href.startswith('/'):
                href = BASE_URL + href
            if href not in project_urls and 'isdb.org' in href:
                project_urls.append(href)
    
    return project_urls


def extract_project_details(url):
    """Extract all details from a project page"""
    content = get_page_content(url)
    if not content:
        return None
    
    soup = BeautifulSoup(content, 'lxml')
    project_data = {
        'url': url,
        'scraped_at': datetime.now().isoformat()
    }
    
    # Extract title
    title = soup.find('h1')
    if title:
        project_data['title'] = title.get_text(strip=True)
    else:
        title = soup.find('title')
        if title:
            project_data['title'] = title.get_text(strip=True)
    
    # Extract meta description
    meta_desc = soup.find('meta', {'name': 'description'})
    if meta_desc:
        project_data['meta_description'] = meta_desc.get('content', '')
    
    # Try to extract structured data from tables
    tables = soup.find_all('table')
    for i, table in enumerate(tables):
        table_data = {}
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                if key and value:
                    table_data[key] = value
        if table_data:
            project_data[f'table_{i+1}_data'] = table_data
    
    # Extract definition lists (dl/dt/dd)
    dls = soup.find_all('dl')
    for i, dl in enumerate(dls):
        dl_data = {}
        dts = dl.find_all('dt')
        dds = dl.find_all('dd')
        for dt, dd in zip(dts, dds):
            key = dt.get_text(strip=True)
            value = dd.get_text(strip=True)
            if key and value:
                dl_data[key] = value
        if dl_data:
            project_data[f'details_{i+1}'] = dl_data
    
    # Extract labeled fields (label + value patterns)
    # Look for common field patterns
    field_patterns = [
        ('Country', ['country', 'location', 'member country']),
        ('Sector', ['sector', 'industry']),
        ('Status', ['status', 'project status']),
        ('Deadline', ['deadline', 'closing date', 'submission deadline']),
        ('Publication Date', ['publication', 'published', 'issue date']),
        ('Contract Type', ['contract type', 'procurement type', 'type']),
        ('Reference', ['reference', 'ref', 'project id', 'tender id']),
        ('Value', ['value', 'amount', 'budget', 'estimated cost']),
        ('Description', ['description', 'summary', 'overview']),
        ('Contact', ['contact', 'focal point', 'email']),
    ]
    
    # Look for labeled content
    for label_elem in soup.find_all(['label', 'strong', 'b', 'span', 'div']):
        label_text = label_elem.get_text(strip=True).lower().rstrip(':')
        for field_name, keywords in field_patterns:
            if any(kw in label_text for kw in keywords):
                # Get the next sibling or parent's text
                next_elem = label_elem.find_next_sibling()
                if next_elem:
                    value = next_elem.get_text(strip=True)
                    if value and field_name not in project_data:
                        project_data[field_name] = value
    
    # Extract all text content from main content area
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    if main_content:
        # Get paragraphs
        paragraphs = main_content.find_all('p')
        content_text = []
        for p in paragraphs[:10]:  # Limit to first 10 paragraphs
            text = p.get_text(strip=True)
            if text and len(text) > 20:
                content_text.append(text)
        if content_text:
            project_data['content_paragraphs'] = content_text
    
    # Extract any download links (documents)
    doc_links = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']):
            doc_links.append({
                'text': link.get_text(strip=True),
                'url': href if href.startswith('http') else BASE_URL + href
            })
    if doc_links:
        project_data['documents'] = doc_links
    
    # Extract dates mentioned
    date_pattern = r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}'
    dates_found = re.findall(date_pattern, str(soup))
    if dates_found:
        project_data['dates_mentioned'] = list(set(dates_found))
    
    return project_data


def scrape_all_tenders():
    """Main function to scrape all tenders"""
    print("=" * 60)
    print("IsDB Tenders Scraper")
    print("=" * 60)
    
    print(f"\n[1] Fetching main tenders page: {TENDERS_URL}")
    
    # First, get the main page content
    main_content = get_page_content(TENDERS_URL)
    if not main_content:
        print("ERROR: Could not fetch the main tenders page")
        return []
    
    print(f"    ✓ Main page fetched successfully")
    
    # Save raw HTML for debugging
    with open('/workspace/tenders_page_raw.html', 'w', encoding='utf-8') as f:
        f.write(main_content)
    print(f"    ✓ Raw HTML saved to tenders_page_raw.html")
    
    # Parse the page
    soup = BeautifulSoup(main_content, 'lxml')
    
    # Print page title
    title = soup.find('title')
    if title:
        print(f"    Page title: {title.get_text(strip=True)}")
    
    # Find all links and analyze the page structure
    print(f"\n[2] Analyzing page structure...")
    
    all_links = soup.find_all('a', href=True)
    print(f"    Total links found: {len(all_links)}")
    
    # Categorize links
    project_links = []
    for link in all_links:
        href = link['href']
        text = link.get_text(strip=True)
        
        # Look for project-related links
        if any(keyword in href.lower() for keyword in ['project', 'tender', 'procurement', 'bid', 'notice']):
            if href.startswith('/'):
                full_url = BASE_URL + href
            elif href.startswith('http'):
                full_url = href
            else:
                full_url = BASE_URL + '/' + href
            
            if full_url not in [p['url'] for p in project_links]:
                project_links.append({
                    'url': full_url,
                    'text': text
                })
    
    print(f"    Project-related links found: {len(project_links)}")
    
    # Also look for tender items in common structures
    # Check for card/list items
    tender_items = soup.select('.tender-item, .project-item, .card, .list-item, .views-row, tr')
    print(f"    Potential tender container elements: {len(tender_items)}")
    
    # Extract and display found links
    if project_links:
        print(f"\n[3] Project links found:")
        for i, link in enumerate(project_links[:20], 1):  # Show first 20
            print(f"    {i}. {link['text'][:50]}..." if len(link['text']) > 50 else f"    {i}. {link['text']}")
            print(f"       URL: {link['url']}")
    
    # Now scrape each project
    all_projects = []
    
    if project_links:
        print(f"\n[4] Scraping individual project pages...")
        for i, link in enumerate(project_links, 1):
            print(f"    [{i}/{len(project_links)}] Scraping: {link['url'][:60]}...")
            
            project_data = extract_project_details(link['url'])
            if project_data:
                project_data['link_text'] = link['text']
                all_projects.append(project_data)
                print(f"        ✓ Extracted: {project_data.get('title', 'No title')[:50]}")
            else:
                print(f"        ✗ Failed to extract data")
            
            # Be polite - don't hammer the server
            time.sleep(1)
    
    # Save results
    print(f"\n[5] Saving results...")
    
    # Save as JSON
    output_file = '/workspace/isdb_tenders_data.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_projects, f, indent=2, ensure_ascii=False)
    print(f"    ✓ Saved {len(all_projects)} projects to {output_file}")
    
    # Create a summary
    print(f"\n{'=' * 60}")
    print(f"SCRAPING COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total projects scraped: {len(all_projects)}")
    
    return all_projects


if __name__ == "__main__":
    projects = scrape_all_tenders()
    
    # Print summary of scraped data
    if projects:
        print(f"\n\nSAMPLE DATA (First project):")
        print("-" * 40)
        print(json.dumps(projects[0], indent=2, ensure_ascii=False)[:2000])
