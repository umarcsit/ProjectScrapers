#!/usr/bin/env python3
"""
BrightSpyre Tender Scraper
Scrapes tender information from https://resume.brightspyre.com/jobs?category=604
Extracts tender details from listing page and detailed description from each tender's detail page.

Author: Auto-generated
"""

import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import html
from urllib.parse import urljoin

# Configuration
BASE_URL = "https://resume.brightspyre.com"
TENDER_URL = f"{BASE_URL}/jobs?category=604"
OUTPUT_CSV = "tender_data.csv"

# Control variables
MAX_RECORDS = None  # Set to a number to limit records (e.g., 10), None for all records
DELAY_BETWEEN_REQUESTS = 1  # Seconds delay between requests to be polite to the server

# Headers for requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def clean_text(text):
    """Clean and normalize text content."""
    if not text:
        return ""
    # Decode HTML entities
    text = html.unescape(text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_description_from_detail_page(detail_url):
    """
    Visit the detail page and extract the full description from 
    <div property="description" class="col-md-12 description">
    """
    try:
        print(f"  Fetching detail page: {detail_url}")
        response = requests.get(detail_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the description div
        description_div = soup.find('div', {'property': 'description', 'class': 'col-md-12 description'})
        
        if description_div:
            # Get all text content, preserving some structure
            description_text = description_div.get_text(separator=' ', strip=True)
            return clean_text(description_text)
        
        return ""
    except Exception as e:
        print(f"  Error fetching detail page: {e}")
        return ""


def extract_additional_info_from_detail_page(detail_url):
    """
    Extract additional information from detail page like:
    - View count
    - Category
    - Type
    - Positions
    - Attached files
    """
    additional_info = {
        'views': '',
        'category': '',
        'type': '',
        'positions': '',
        'attached_files': ''
    }
    
    try:
        response = requests.get(detail_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract view count
        views_span = soup.find('span', class_='text-muted pull-right')
        if views_span:
            views_text = views_span.get_text(strip=True)
            views_match = re.search(r'(\d+)', views_text)
            if views_match:
                additional_info['views'] = views_match.group(1)
        
        # Extract info from table
        info_table = soup.find('table', class_='info-table-detail')
        if info_table:
            rows = info_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                for i, cell in enumerate(cells):
                    cell_text = cell.get_text(strip=True)
                    if 'Category' in cell_text and i + 1 < len(cells):
                        additional_info['category'] = clean_text(cells[i + 1].get_text(strip=True))
                    elif 'Type' in cell_text and i + 1 < len(cells):
                        additional_info['type'] = clean_text(cells[i + 1].get_text(strip=True))
                    elif 'Position' in cell_text and i + 1 < len(cells):
                        additional_info['positions'] = clean_text(cells[i + 1].get_text(strip=True))
        
        # Extract attached files
        files_list = []
        file_links = soup.select('a[download="download"]')
        for link in file_links:
            file_name = link.get_text(strip=True)
            file_url = link.get('href', '')
            if file_name:
                files_list.append(f"{file_name} ({file_url})")
        additional_info['attached_files'] = ' | '.join(files_list)
        
    except Exception as e:
        print(f"  Error extracting additional info: {e}")
    
    return additional_info


def get_total_records_count(soup):
    """Get total number of tender records available."""
    # Look for the category count in the sidebar
    category_items = soup.select('ul.categories li.item a[href*="category=604"]')
    for item in category_items:
        label = item.find('label')
        if label:
            text = label.get_text(strip=True)
            match = re.search(r'\((\d+)\)', text)
            if match:
                return int(match.group(1))
    return 0


def scrape_listing_page(page_url):
    """Scrape tender listings from a single page."""
    tenders = []
    
    try:
        print(f"Fetching listing page: {page_url}")
        response = requests.get(page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all tender items - they are in divs with class "row display-table background-color-white cards-shade margin-bottom-ten"
        tender_items = soup.find_all('div', class_='row display-table background-color-white cards-shade margin-bottom-ten')
        
        for item in tender_items:
            tender = {}
            
            # Extract title and link
            title_link = item.find('a', class_='text-decoration-none title-job')
            if title_link:
                tender['title'] = clean_text(title_link.get_text())
                href = title_link.get('href', '')
                tender['detail_url'] = urljoin(BASE_URL, href) if href else ''
            else:
                tender['title'] = ''
                tender['detail_url'] = ''
            
            # Extract organization info
            org_div = item.find('div', property='hiringOrganization')
            if org_div:
                # Organization name
                org_name_span = org_div.find('span', property='name')
                tender['organization_name'] = clean_text(org_name_span.get_text()) if org_name_span else ''
                
            else:
                tender['organization_name'] = ''
            
            # Extract organization link (separate location)
            org_link = item.select_one('div.col-md-12 b span[type="PropertyValue"] a')
            if org_link:
                tender['organization_url'] = org_link.get('href', '')
                if not tender['organization_name']:
                    tender['organization_name'] = clean_text(org_link.get_text())
            else:
                tender['organization_url'] = ''
            
            # Extract last date to apply (validThrough)
            valid_through = item.find('span', property='validThrough')
            tender['last_date_to_apply'] = clean_text(valid_through.get_text()) if valid_through else ''
            
            # Extract date posted
            date_posted = item.find('span', property='datePosted')
            tender['date_posted'] = clean_text(date_posted.get_text()) if date_posted else ''
            
            # Extract short description from listing
            short_desc = item.find('span', property='description')
            tender['short_description'] = clean_text(short_desc.get_text()) if short_desc else ''
            
            # Extract category/employment type
            employment_type = item.find('span', property='employmentType')
            tender['employment_type'] = clean_text(employment_type.get_text()) if employment_type else ''
            
            # Extract occupational category
            occ_category = item.find('span', property='occupationalCategory')
            tender['category'] = clean_text(occ_category.get_text()) if occ_category else ''
            
            tenders.append(tender)
        
        return tenders, soup
        
    except Exception as e:
        print(f"Error scraping listing page: {e}")
        return [], None


def scrape_all_tenders():
    """Main function to scrape all tenders with pagination support."""
    all_tenders = []
    page = 1
    total_records = 0
    
    while True:
        # Build page URL
        if page == 1:
            page_url = TENDER_URL
        else:
            page_url = f"{TENDER_URL}&page={page}"
        
        tenders, soup = scrape_listing_page(page_url)
        
        if page == 1 and soup:
            total_records = get_total_records_count(soup)
            print(f"\n{'='*60}")
            print(f"TOTAL RECORDS AVAILABLE: {total_records}")
            print(f"{'='*60}\n")
        
        if not tenders:
            print(f"No tenders found on page {page}. Stopping.")
            break
        
        all_tenders.extend(tenders)
        print(f"Page {page}: Found {len(tenders)} tenders (Total so far: {len(all_tenders)})")
        
        # Check if we've reached MAX_RECORDS limit
        if MAX_RECORDS and len(all_tenders) >= MAX_RECORDS:
            all_tenders = all_tenders[:MAX_RECORDS]
            print(f"Reached MAX_RECORDS limit of {MAX_RECORDS}")
            break
        
        # Check if we've scraped all available records
        if len(all_tenders) >= total_records:
            print(f"Scraped all {total_records} available records.")
            break
        
        # Check for pagination - look for next page link
        pagination = soup.find('div', class_='pagination') if soup else None
        next_link = None
        if pagination:
            next_link = pagination.find('a', text=re.compile(r'»|Next|next'))
        
        if not next_link and len(tenders) < 10:  # Assuming ~10 items per page
            print("No more pages detected.")
            break
        
        page += 1
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    return all_tenders, total_records


def enrich_with_detail_pages(tenders):
    """Visit each tender's detail page to get full description and additional info."""
    enriched_tenders = []
    
    for i, tender in enumerate(tenders):
        print(f"\nProcessing tender {i+1}/{len(tenders)}: {tender.get('title', 'Unknown')[:50]}...")
        
        if tender.get('detail_url'):
            # Get full description
            description = extract_description_from_detail_page(tender['detail_url'])
            tender['description'] = description
            
            # Get additional info
            additional_info = extract_additional_info_from_detail_page(tender['detail_url'])
            tender['views'] = additional_info.get('views', '')
            tender['type'] = additional_info.get('type', '')
            tender['positions'] = additional_info.get('positions', '')
            tender['attached_files'] = additional_info.get('attached_files', '')
            
            # Update category if not already set
            if not tender.get('category') and additional_info.get('category'):
                tender['category'] = additional_info['category']
        else:
            tender['description'] = ''
            tender['views'] = ''
            tender['type'] = ''
            tender['positions'] = ''
            tender['attached_files'] = ''
        
        enriched_tenders.append(tender)
        
        # Delay between requests
        if i < len(tenders) - 1:
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    return enriched_tenders


def save_to_csv(tenders, output_file):
    """Save tenders to CSV file."""
    if not tenders:
        print("No tenders to save.")
        return
    
    # Define column order for better readability
    columns = [
        'title',
        'organization_name',
        'organization_url',
        'detail_url',
        'date_posted',
        'last_date_to_apply',
        'category',
        'type',
        'positions',
        'views',
        'short_description',
        'description',
        'attached_files',
        'employment_type'
    ]
    
    # Ensure all columns exist in all rows
    for tender in tenders:
        for col in columns:
            if col not in tender:
                tender[col] = ''
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(tenders)
    
    print(f"\nSaved {len(tenders)} tenders to {output_file}")


def main():
    """Main entry point."""
    print("="*60)
    print("BrightSpyre Tender Scraper")
    print("="*60)
    print(f"Target URL: {TENDER_URL}")
    print(f"Max Records: {MAX_RECORDS if MAX_RECORDS else 'All'}")
    print(f"Delay between requests: {DELAY_BETWEEN_REQUESTS}s")
    print("="*60 + "\n")
    
    # Step 1: Scrape listing pages
    print("STEP 1: Scraping listing pages...")
    tenders, total_records = scrape_all_tenders()
    
    if not tenders:
        print("No tenders found. Exiting.")
        return
    
    print(f"\nFound {len(tenders)} tenders from listing pages.")
    
    # Step 2: Enrich with detail page information
    print("\nSTEP 2: Fetching detail pages for full descriptions...")
    enriched_tenders = enrich_with_detail_pages(tenders)
    
    # Step 3: Save to CSV
    print("\nSTEP 3: Saving to CSV...")
    save_to_csv(enriched_tenders, OUTPUT_CSV)
    
    # Summary
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"Total records available on website: {total_records}")
    print(f"Total records scraped: {len(enriched_tenders)}")
    print(f"Output file: {OUTPUT_CSV}")
    print("="*60)


if __name__ == "__main__":
    main()
