#!/usr/bin/env python3
"""
African Development Bank Corporate Procurement Scraper

This script extracts project information and descriptions from the AfDB
corporate procurement page: https://www.afdb.org/en/about-us/corporate-procurement
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import re
from datetime import datetime
from urllib.parse import urljoin
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://www.afdb.org"
PROCUREMENT_URL = f"{BASE_URL}/en/about-us/corporate-procurement"


class AfDBScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
    
    def fetch_page(self, url, retries=3):
        for attempt in range(retries):
            try:
                logger.info(f"Fetching: {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.text, 'html.parser')
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        return None

    def extract_main_page_info(self, soup):
        info = {'page_title': '', 'page_description': '', 'sections': [], 'links': []}
        
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            info['page_title'] = title_tag.get_text(strip=True)
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            info['page_description'] = meta_desc.get('content', '')
        
        main_content = soup.find('main') or soup.find('div', class_=re.compile(r'content|main', re.I))
        if main_content:
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
                if section['content']:
                    info['sections'].append(section)
            
            if not info['sections']:
                for p in main_content.find_all('p'):
                    text = p.get_text(strip=True)
                    if text and len(text) > 50:
                        info['sections'].append({'title': 'Content', 'content': [text]})
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            keywords = ['procurement', 'tender', 'bid', 'contract', 'project']
            if any(k in href.lower() or k in text.lower() for k in keywords):
                full_url = urljoin(BASE_URL, href)
                if full_url not in [l['url'] for l in info['links']]:
                    info['links'].append({'text': text, 'url': full_url})
        
        return info

    def extract_project_details(self, url):
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
        
        content_area = soup.find('article') or soup.find('div', class_=re.compile(r'content|main', re.I))
        if content_area:
            if not project['description']:
                paragraphs = content_area.find_all('p')
                project['description'] = ' '.join([p.get_text(strip=True) for p in paragraphs[:3]])
            
            for table in content_area.find_all('table'):
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key and value:
                            project['details'][key] = value
            
            for link in content_area.find_all('a', href=True):
                href = link.get('href', '')
                if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xls']):
                    project['documents'].append({
                        'name': link.get_text(strip=True),
                        'url': urljoin(BASE_URL, href)
                    })
        
        return project

    def extract_opportunities(self, soup):
        opportunities = []
        
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
        
        for card in soup.find_all(['div', 'article'], class_=re.compile(r'card|item|tender|project', re.I)):
            title_tag = card.find(['h2', 'h3', 'h4', 'a'])
            if title_tag:
                opp = {'title': title_tag.get_text(strip=True)}
                link = card.find('a', href=True)
                if link:
                    opp['url'] = urljoin(BASE_URL, link['href'])
                desc = card.find('p')
                if desc:
                    opp['description'] = desc.get_text(strip=True)
                opportunities.append(opp)
        
        return opportunities

    def scrape(self):
        logger.info("Starting AfDB Corporate Procurement scraping...")
        
        result = {
            'source_url': PROCUREMENT_URL,
            'scraped_at': datetime.now().isoformat(),
            'main_page_info': {},
            'procurement_opportunities': [],
            'project_details': []
        }
        
        base_soup = self.fetch_page(BASE_URL)
        if base_soup:
            time.sleep(1)
        
        soup = self.fetch_page(PROCUREMENT_URL)
        if not soup:
            logger.error("Failed to fetch main procurement page")
            return result
        
        result['main_page_info'] = self.extract_main_page_info(soup)
        result['procurement_opportunities'] = self.extract_opportunities(soup)
        
        project_links = [l for l in result['main_page_info'].get('links', []) 
                         if 'project' in l.get('url', '').lower() or 'tender' in l.get('url', '').lower()]
        
        for link in project_links[:10]:
            detail = self.extract_project_details(link['url'])
            if detail:
                result['project_details'].append(detail)
                time.sleep(1)
        
        return result


def save_to_json(data, filename='afdb_procurement_data.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Data saved to {filename}")


def save_to_csv(data, filename='afdb_procurement_data.csv'):
    rows = []
    for section in data.get('main_page_info', {}).get('sections', []):
        rows.append({'type': 'section', 'title': section['title'], 
                     'content': ' | '.join(section['content']), 'url': data['source_url']})
    
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
        rows.append({'type': 'project', 'title': project['title'],
                     'description': project['description'], 'url': project['url'],
                     'details': json.dumps(project.get('details', {}))})
    
    if rows:
        fieldnames = set()
        for row in rows:
            fieldnames.update(row.keys())
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"Data saved to {filename}")


def main():
    print("=" * 60)
    print("AfDB Corporate Procurement Scraper")
    print("=" * 60)
    print(f"\nTarget URL: {PROCUREMENT_URL}\n")
    
    scraper = AfDBScraper()
    data = scraper.scrape()
    
    save_to_json(data)
    save_to_csv(data)
    
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Source: {data['source_url']}")
    print(f"Scraped at: {data['scraped_at']}")
    print(f"Page Title: {data['main_page_info'].get('page_title', 'N/A')}")
    print(f"Sections: {len(data['main_page_info'].get('sections', []))}")
    print(f"Links: {len(data['main_page_info'].get('links', []))}")
    print(f"Opportunities: {len(data['procurement_opportunities'])}")
    print(f"Project details: {len(data['project_details'])}")
    
    for section in data['main_page_info'].get('sections', []):
        print(f"\n### {section['title']}")
        for content in section['content'][:3]:
            print(f"  - {content[:150]}..." if len(content) > 150 else f"  - {content}")
    
    print("\nOutput: afdb_procurement_data.json, afdb_procurement_data.csv")


if __name__ == "__main__":
    main()
