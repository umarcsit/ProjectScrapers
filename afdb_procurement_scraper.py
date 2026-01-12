#!/usr/bin/env python3
"""
African Development Bank Corporate Procurement Scraper

This script extracts project information and descriptions from the AfDB
corporate procurement page: https://www.afdb.org/en/about-us/corporate-procurement

Uses multiple approaches to bypass anti-bot protection:
1. CloudScraper - bypasses Cloudflare and similar protections
2. Selenium - uses real browser as fallback
"""

import json
import csv
import time
import re
from datetime import datetime
from urllib.parse import urljoin
import logging

# Try importing different scraping libraries
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://www.afdb.org"
PROCUREMENT_URL = f"{BASE_URL}/en/about-us/corporate-procurement"


class CloudScraperFetcher:
    """Fetcher using CloudScraper to bypass anti-bot protection."""
    
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            },
            delay=10
        )
    
    def fetch(self, url):
        try:
            logger.info(f"[CloudScraper] Fetching: {url}")
            response = self.scraper.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
            logger.warning(f"[CloudScraper] Status code: {response.status_code}")
        except Exception as e:
            logger.warning(f"[CloudScraper] Error: {e}")
        return None


class SeleniumFetcher:
    """Fetcher using Selenium with headless Chrome."""
    
    def __init__(self):
        self.driver = None
    
    def _init_driver(self):
        if self.driver is None:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            except Exception:
                self.driver = webdriver.Chrome(options=options)
    
    def fetch(self, url):
        try:
            self._init_driver()
            logger.info(f"[Selenium] Fetching: {url}")
            self.driver.get(url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # Wait for dynamic content
            return self.driver.page_source
        except Exception as e:
            logger.warning(f"[Selenium] Error: {e}")
        return None
    
    def close(self):
        if self.driver:
            self.driver.quit()


class AfDBScraper:
    """Main scraper class with multiple fetching strategies."""
    
    def __init__(self):
        self.fetchers = []
        
        if HAS_CLOUDSCRAPER:
            self.fetchers.append(('CloudScraper', CloudScraperFetcher()))
            logger.info("CloudScraper available")
        
        if HAS_SELENIUM:
            self.fetchers.append(('Selenium', SeleniumFetcher()))
            logger.info("Selenium available")
        
        if not self.fetchers:
            logger.error("No fetchers available! Install cloudscraper or selenium.")
    
    def fetch_page(self, url):
        """Try each fetcher until one succeeds."""
        for name, fetcher in self.fetchers:
            html = fetcher.fetch(url)
            if html and len(html) > 1000:  # Ensure we got real content
                logger.info(f"[{name}] Successfully fetched {len(html)} bytes")
                return BeautifulSoup(html, 'html.parser')
        return None

    def extract_main_page_info(self, soup):
        """Extract general information from the main corporate procurement page."""
        info = {'page_title': '', 'page_description': '', 'sections': [], 'links': []}
        
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            info['page_title'] = title_tag.get_text(strip=True)
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            info['page_description'] = meta_desc.get('content', '')
        
        # Try multiple content selectors
        main_content = (
            soup.find('main') or 
            soup.find('article') or
            soup.find('div', class_=re.compile(r'field--name-body|content|main', re.I)) or
            soup.find('div', id=re.compile(r'content|main', re.I))
        )
        
        if main_content:
            # Extract headers and their content
            for header in main_content.find_all(['h2', 'h3', 'h4']):
                section = {'title': header.get_text(strip=True), 'content': []}
                for sibling in header.find_next_siblings():
                    if sibling.name in ['h2', 'h3', 'h4']:
                        break
                    if sibling.name == 'p':
                        text = sibling.get_text(strip=True)
                        if text:
                            section['content'].append(text)
                    elif sibling.name in ['ul', 'ol']:
                        items = [li.get_text(strip=True) for li in sibling.find_all('li')]
                        section['content'].extend(items)
                    elif sibling.name == 'div':
                        text = sibling.get_text(strip=True)
                        if text and len(text) > 20:
                            section['content'].append(text)
                if section['content']:
                    info['sections'].append(section)
            
            # If no sections found, get all paragraphs
            if not info['sections']:
                for p in main_content.find_all('p'):
                    text = p.get_text(strip=True)
                    if text and len(text) > 30:
                        info['sections'].append({'title': 'Content', 'content': [text]})
        
        # Also try to get content from body if main_content failed
        if not info['sections']:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if text and len(text) > 50:
                    info['sections'].append({'title': 'Page Content', 'content': [text]})
        
        # Extract all links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            keywords = ['procurement', 'tender', 'bid', 'contract', 'project', 'opportunity', 'rfp', 'rfq']
            if any(k in href.lower() or k in text.lower() for k in keywords):
                full_url = urljoin(BASE_URL, href)
                if full_url not in [l['url'] for l in info['links']] and text:
                    info['links'].append({'text': text, 'url': full_url})
        
        return info

    def extract_project_details(self, url):
        """Extract detailed information from a project/tender page."""
        soup = self.fetch_page(url)
        if not soup:
            return None
        
        project = {'url': url, 'title': '', 'description': '', 'details': {}, 'documents': []}
        
        title_tag = soup.find('h1') or soup.find('h2')
        if title_tag:
            project['title'] = title_tag.get_text(strip=True)
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            project['description'] = meta_desc.get('content', '')
        
        content_area = (
            soup.find('article') or 
            soup.find('div', class_=re.compile(r'field--name-body|content|main', re.I))
        )
        
        if content_area:
            if not project['description']:
                paragraphs = content_area.find_all('p')
                project['description'] = ' '.join([p.get_text(strip=True) for p in paragraphs[:5]])
            
            # Extract table data
            for table in content_area.find_all('table'):
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key and value:
                            project['details'][key] = value
            
            # Extract documents
            for link in content_area.find_all('a', href=True):
                href = link.get('href', '')
                if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']):
                    project['documents'].append({
                        'name': link.get_text(strip=True) or 'Document',
                        'url': urljoin(BASE_URL, href)
                    })
        
        return project

    def extract_opportunities(self, soup):
        """Extract procurement opportunities from the page."""
        opportunities = []
        
        # Pattern 1: Tables
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            headers = []
            header_row = table.find('tr')
            if header_row:
                headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
            
            for row in rows[1:]:
                cells = row.find_all('td')
                if cells:
                    opp = {}
                    for i, cell in enumerate(cells):
                        key = headers[i] if i < len(headers) else f'col_{i}'
                        link = cell.find('a', href=True)
                        if link:
                            opp[key] = {'text': cell.get_text(strip=True), 'url': urljoin(BASE_URL, link['href'])}
                        else:
                            opp[key] = cell.get_text(strip=True)
                    if opp:
                        opportunities.append(opp)
        
        # Pattern 2: Cards/Items
        for card in soup.find_all(['div', 'article', 'li'], class_=re.compile(r'card|item|tender|project|view-row|node', re.I)):
            title_tag = card.find(['h2', 'h3', 'h4', 'a', 'strong'])
            if title_tag:
                text = title_tag.get_text(strip=True)
                if text and len(text) > 5:
                    opp = {'title': text}
                    link = card.find('a', href=True)
                    if link:
                        opp['url'] = urljoin(BASE_URL, link['href'])
                    desc = card.find('p') or card.find('div', class_=re.compile(r'desc|summary|body', re.I))
                    if desc:
                        opp['description'] = desc.get_text(strip=True)
                    opportunities.append(opp)
        
        return opportunities

    def scrape(self):
        """Main scraping function."""
        logger.info("Starting AfDB Corporate Procurement scraping...")
        
        result = {
            'source_url': PROCUREMENT_URL,
            'scraped_at': datetime.now().isoformat(),
            'main_page_info': {},
            'procurement_opportunities': [],
            'project_details': []
        }
        
        # Fetch main procurement page
        soup = self.fetch_page(PROCUREMENT_URL)
        if not soup:
            logger.error("Failed to fetch main procurement page")
            return result
        
        result['main_page_info'] = self.extract_main_page_info(soup)
        logger.info(f"Extracted {len(result['main_page_info']['sections'])} sections")
        
        result['procurement_opportunities'] = self.extract_opportunities(soup)
        logger.info(f"Found {len(result['procurement_opportunities'])} opportunities")
        
        # Follow project links
        project_links = [l for l in result['main_page_info'].get('links', []) 
                         if any(k in l.get('url', '').lower() for k in ['project', 'tender', 'opportunity'])]
        
        for link in project_links[:5]:  # Limit to avoid overloading
            detail = self.extract_project_details(link['url'])
            if detail and detail.get('title'):
                result['project_details'].append(detail)
                time.sleep(2)
        
        logger.info(f"Extracted {len(result['project_details'])} project details")
        return result
    
    def close(self):
        """Clean up resources."""
        for name, fetcher in self.fetchers:
            if hasattr(fetcher, 'close'):
                fetcher.close()


def save_to_json(data, filename='afdb_procurement_data.json'):
    """Save data to JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved to {filename}")


def save_to_csv(data, filename='afdb_procurement_data.csv'):
    """Save data to CSV file."""
    rows = []
    
    for section in data.get('main_page_info', {}).get('sections', []):
        rows.append({
            'type': 'section',
            'title': section['title'],
            'content': ' | '.join(section['content']),
            'url': data['source_url']
        })
    
    for opp in data.get('procurement_opportunities', []):
        row = {'type': 'opportunity'}
        for key, value in opp.items():
            if isinstance(value, dict):
                row[key] = value.get('text', str(value))
                row[f'{key}_url'] = value.get('url', '')
            else:
                row[key] = value
        rows.append(row)
    
    for project in data.get('project_details', []):
        rows.append({
            'type': 'project',
            'title': project.get('title', ''),
            'description': project.get('description', ''),
            'url': project.get('url', ''),
            'details': json.dumps(project.get('details', {})),
            'documents': json.dumps(project.get('documents', []))
        })
    
    if rows:
        fieldnames = set()
        for row in rows:
            fieldnames.update(row.keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"Saved to {filename}")


def main():
    print("=" * 70)
    print("AfDB Corporate Procurement Scraper")
    print("=" * 70)
    print(f"Target URL: {PROCUREMENT_URL}")
    print(f"Methods: CloudScraper={HAS_CLOUDSCRAPER}, Selenium={HAS_SELENIUM}")
    print("=" * 70 + "\n")
    
    scraper = AfDBScraper()
    
    try:
        data = scraper.scrape()
        
        save_to_json(data)
        save_to_csv(data)
        
        print("\n" + "=" * 70)
        print("EXTRACTION RESULTS")
        print("=" * 70)
        print(f"Source: {data['source_url']}")
        print(f"Scraped at: {data['scraped_at']}")
        print(f"Page Title: {data['main_page_info'].get('page_title', 'N/A')}")
        print(f"Description: {data['main_page_info'].get('page_description', 'N/A')[:100]}...")
        print(f"Sections: {len(data['main_page_info'].get('sections', []))}")
        print(f"Links: {len(data['main_page_info'].get('links', []))}")
        print(f"Opportunities: {len(data['procurement_opportunities'])}")
        print(f"Project Details: {len(data['project_details'])}")
        
        print("\n" + "-" * 70)
        print("CONTENT PREVIEW")
        print("-" * 70)
        for section in data['main_page_info'].get('sections', [])[:5]:
            print(f"\n### {section['title']}")
            for content in section['content'][:2]:
                preview = content[:200] + "..." if len(content) > 200 else content
                print(f"  {preview}")
        
        print("\n" + "-" * 70)
        print("Output Files: afdb_procurement_data.json, afdb_procurement_data.csv")
        print("-" * 70)
        
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
