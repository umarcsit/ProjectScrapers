#!/usr/bin/env python3
"""
IsDB Tenders Scraper v2
Extracts structured tender information from https://www.isdb.org/project-procurement/tenders
Outputs: JSON (full data) and CSV (clean formatted data)
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import csv
from datetime import datetime

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


def clean_field(value, prefix):
    """Remove prefix from field value"""
    if value and value.startswith(prefix):
        return value.replace(prefix, '').strip()
    return value


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


def save_to_json(tenders, filename):
    """Save tenders to JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(tenders, f, indent=2, ensure_ascii=False)
    print(f"    Saved: {filename}")


def save_to_csv(tenders, filename):
    """Save tenders to comprehensive CSV file with clean text"""
    
    # Define all fields for CSV
    fieldnames = [
        'title',
        'status', 
        'tender_type',
        'country',
        'close_date',
        'url',
        'node_id',
        'full_title',
        'notice_type',
        'issue_date',
        'project_code',
        'project_title',
        'contact_email',
        'description',
        'attachments',
        'all_emails',
        'contract_award_company',
        'contract_award_country',
        'contract_award_address'
    ]
    
    # Process and flatten data
    cleaned_data = []
    
    for tender in tenders:
        row = {
            'title': tender.get('title', ''),
            'status': tender.get('status', ''),
            'tender_type': tender.get('tender_type', ''),
            'country': tender.get('country', ''),
            'close_date': tender.get('close_date', ''),
            'url': tender.get('url', ''),
            'node_id': tender.get('node_id', ''),
        }
        
        # Extract details
        details = tender.get('details', {})
        
        row['full_title'] = details.get('full_title', '')
        
        # Clean notice type
        row['notice_type'] = clean_field(details.get('notice_type', ''), 'Notice Type')
        
        # Clean issue date
        row['issue_date'] = clean_field(details.get('issue_date', ''), 'Issue Date')
        
        # Clean project code
        row['project_code'] = clean_field(details.get('project_code', ''), 'Project code')
        
        # Clean project title
        row['project_title'] = clean_field(details.get('project_title', ''), 'Project title')
        
        # Clean email
        row['contact_email'] = clean_field(details.get('email', ''), 'Email')
        
        # Description (clean text)
        row['description'] = details.get('description', '')
        
        # Attachments as list
        attachments = details.get('attachments', [])
        if attachments:
            att_list = [f"{a.get('name', '')} ({a.get('url', '')})" for a in attachments]
            row['attachments'] = ' | '.join(att_list)
        else:
            row['attachments'] = ''
        
        # All emails found
        emails = details.get('emails_found', [])
        row['all_emails'] = ', '.join(emails) if emails else ''
        
        # Contract award info
        row['contract_award_company'] = clean_field(
            details.get('contract_award_name', ''), 'Contract Award Company Name')
        row['contract_award_country'] = clean_field(
            details.get('contract_award_country', ''), 'Contract Award Company Country')
        row['contract_award_address'] = clean_field(
            details.get('contract_award_address', ''), 'Contract Award Company Address')
        
        cleaned_data.append(row)
    
    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_data)
    
    print(f"    Saved: {filename} ({len(fieldnames)} columns)")


def main():
    """Main scraping function"""
    print("=" * 70)
    print("IsDB Tenders Scraper v2")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Step 1: Get all tenders from listing pages
    print("[1] Fetching tender listings...")
    all_tenders = get_all_pages()
    print(f"\n    Total: {len(all_tenders)} tenders\n")
    
    if not all_tenders:
        print("ERROR: No tenders found!")
        return
    
    # Step 2: Get detailed information for each tender
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
    
    # Step 3: Save results
    print(f"\n[3] Saving results...")
    
    # Save JSON (full data)
    save_to_json(all_tenders, 'isdb_tenders_full.json')
    
    # Save CSV (clean formatted data)
    save_to_csv(all_tenders, 'isdb_tenders_complete.csv')
    
    # Summary statistics
    print(f"\n{'=' * 70}")
    print(f"SCRAPING COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total tenders: {len(all_tenders)}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Country breakdown
    countries = {}
    for t in all_tenders:
        c = t.get('country', 'Unknown')
        countries[c] = countries.get(c, 0) + 1
    
    print(f"\nTenders by Country:")
    for country, count in sorted(countries.items(), key=lambda x: -x[1])[:10]:
        print(f"  {country}: {count}")
    
    # Type breakdown
    types = {}
    for t in all_tenders:
        tt = t.get('tender_type', 'Unknown')
        types[tt] = types.get(tt, 0) + 1
    
    print(f"\nTenders by Type:")
    for ttype, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {ttype}: {count}")
    
    # Sample data
    print(f"\nSample Tenders:")
    for i, t in enumerate(all_tenders[:3], 1):
        print(f"\n{i}. {t.get('title', 'N/A')[:60]}")
        print(f"   Country: {t.get('country', 'N/A')} | Type: {t.get('tender_type', 'N/A')}")
        print(f"   Status: {t.get('status', 'N/A')} | Close: {t.get('close_date', 'N/A')}")
        if t.get('details', {}).get('project_code'):
            code = clean_field(t['details']['project_code'], 'Project code')
            print(f"   Project Code: {code}")
    
    return all_tenders


if __name__ == "__main__":
    main()
