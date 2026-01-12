#!/usr/bin/env python3
"""
IsDB Tenders Scraper v2
Properly extracts structured tender information from https://www.isdb.org/project-procurement/tenders
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime
import csv

# Base URL
BASE_URL = "https://www.isdb.org"
TENDERS_URL = f"{BASE_URL}/project-procurement/tenders"

# Headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def get_page_content(url, retries=3):
    """Fetch page content with retries"""
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"    Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    return None


def extract_tenders_from_listing(content):
    """Extract tender items from the listing page"""
    soup = BeautifulSoup(content, 'lxml')
    tenders = []
    
    # Find all tender articles
    articles = soup.find_all('article', class_='type-tender')
    
    for article in articles:
        tender = {}
        
        # Get URL and title
        title_link = article.find('h2')
        if title_link:
            a_tag = title_link.find('a')
            if a_tag:
                tender['title'] = a_tag.get_text(strip=True)
                href = a_tag.get('href', '')
                tender['url'] = BASE_URL + href if href.startswith('/') else href
        
        # Get status
        status_field = article.find('div', class_='field--name-field-tender-status')
        if status_field:
            tender['status'] = status_field.get_text(strip=True)
        
        # Get tender type
        type_field = article.find('div', class_='field--name-field-tender-type')
        if type_field:
            tender['tender_type'] = type_field.get_text(strip=True)
        
        # Get country
        country_field = article.find('div', class_='field--name-field-world-country')
        if country_field:
            tender['country'] = country_field.get_text(strip=True)
        
        # Get close date
        date_field = article.find('div', class_='field--name-field-close-date')
        if date_field:
            time_tag = date_field.find('time')
            if time_tag:
                tender['close_date'] = time_tag.get_text(strip=True)
        
        tender['node_id'] = article.get('data-nid', '')
        
        if tender.get('title'):
            tenders.append(tender)
    
    return tenders


def extract_project_details(url):
    """Extract detailed information from a tender detail page"""
    content = get_page_content(url)
    if not content:
        return None
    
    soup = BeautifulSoup(content, 'lxml')
    details = {'detail_url': url}
    
    # Get full title
    title = soup.find('h1')
    if title:
        details['full_title'] = title.get_text(strip=True)
    
    # Get all field containers
    field_containers = soup.find_all('div', class_=re.compile(r'field--name-field-'))
    
    for field in field_containers:
        classes = field.get('class', [])
        field_name = None
        
        for cls in classes:
            if cls.startswith('field--name-field-'):
                field_name = cls.replace('field--name-field-', '').replace('-', '_')
                break
        
        if field_name:
            value = field.get_text(strip=True)
            if value and field_name not in details:
                details[field_name] = value
    
    # Get description/body content
    body = soup.find('div', class_='field--name-body')
    if body:
        paragraphs = body.find_all(['p', 'li'])
        if paragraphs:
            details['description'] = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        else:
            details['description'] = body.get_text(strip=True)
    
    # Get file attachments
    file_links = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip']):
            file_url = href if href.startswith('http') else BASE_URL + href
            file_links.append({
                'name': link.get_text(strip=True) or href.split('/')[-1],
                'url': file_url
            })
    
    if file_links:
        details['attachments'] = file_links
    
    # Extract emails
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = list(set(re.findall(email_pattern, str(soup))))
    if emails:
        details['emails_found'] = emails
    
    return details


def get_all_pages():
    """Get tenders from all pagination pages"""
    all_tenders = []
    page = 0
    
    while True:
        url = TENDERS_URL if page == 0 else f"{TENDERS_URL}?page={page}"
        
        print(f"  Fetching page {page + 1}: {url}")
        content = get_page_content(url)
        
        if not content:
            break
        
        tenders = extract_tenders_from_listing(content)
        
        if not tenders:
            print(f"  No tenders found on page {page + 1}")
            break
        
        print(f"  Found {len(tenders)} tenders")
        all_tenders.extend(tenders)
        
        soup = BeautifulSoup(content, 'lxml')
        next_link = soup.find('a', rel='next') or soup.find('li', class_='pager__item--next')
        
        if not next_link:
            break
        
        page += 1
        time.sleep(1)
        
        if page > 50:
            break
    
    return all_tenders


def main():
    print("=" * 70)
    print("IsDB Tenders Scraper v2")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print("[1] Fetching tender listings...")
    all_tenders = get_all_pages()
    print(f"\n    Total: {len(all_tenders)} tenders\n")
    
    if not all_tenders:
        print("ERROR: No tenders found!")
        return
    
    print("[2] Fetching details for each tender...")
    for i, tender in enumerate(all_tenders, 1):
        url = tender.get('url')
        if url:
            title = tender.get('title', 'Unknown')[:45]
            print(f"    [{i}/{len(all_tenders)}] {title}...")
            details = extract_project_details(url)
            if details:
                tender['details'] = details
            time.sleep(0.5)
    
    print(f"\n[3] Saving results...")
    
    # Save JSON
    with open('/workspace/isdb_tenders_full.json', 'w', encoding='utf-8') as f:
        json.dump(all_tenders, f, indent=2, ensure_ascii=False)
    print("    Saved: isdb_tenders_full.json")
    
    # Save CSV
    with open('/workspace/isdb_tenders_summary.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['title', 'status', 'tender_type', 'country', 'close_date', 'url']
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for tender in all_tenders:
            writer.writerow(tender)
    print("    Saved: isdb_tenders_summary.csv")
    
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {len(all_tenders)} tenders scraped")
    print("=" * 70)
    
    # Show samples
    print("\nSAMPLE DATA:")
    for i, t in enumerate(all_tenders[:3], 1):
        print(f"\n{i}. {t.get('title', 'N/A')[:60]}")
        print(f"   Country: {t.get('country', 'N/A')} | Type: {t.get('tender_type', 'N/A')}")
        print(f"   Status: {t.get('status', 'N/A')} | Close: {t.get('close_date', 'N/A')}")
    
    return all_tenders


if __name__ == "__main__":
    main()
