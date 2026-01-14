"""
Pakistan Tenders Scraper
Scrapes tender information from https://www.tendersontime.com/pakistan-tenders/
Extracts main listing data and detailed description from each tender's detail page.

Author: Auto-generated scraper
Date: 2026-01-14
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
import os

# ============================================
# CONFIGURATION
# ============================================
BASE_URL = "https://www.tendersontime.com/pakistan-tenders/"
MAX_RECORDS = 50  # Maximum number of records to scrape (set to None for all available)
DELAY_BETWEEN_REQUESTS = 1  # Seconds to wait between requests to be polite to the server
OUTPUT_CSV = "pakistan_tenders.csv"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}


def get_soup(url, retries=3):
    """Fetch URL and return BeautifulSoup object with retry logic."""
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'lxml')
        except requests.RequestException as e:
            print(f"  Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  Failed to fetch {url} after {retries} attempts")
                return None
    return None


def parse_listing_page(soup):
    """
    Parse the main listing page and extract tender data.
    Structure: div.listingbox contains each tender listing.
    """
    tenders = []
    
    # Find all tender listing boxes
    listing_boxes = soup.find_all('div', class_='listingbox')
    
    for box in listing_boxes:
        tender = {}
        
        try:
            # Extract title and detail URL from the listing-summary link
            title_link = box.find('a', href=True)
            if title_link:
                tender['Detail_URL'] = title_link.get('href', '')
                summary_elem = title_link.find('p', class_='listing-summary')
                if summary_elem:
                    tender['Title'] = summary_elem.get_text(strip=True)
            
            # Extract deadline from list-data
            deadline_elem = box.find('p', class_='list-data', string=lambda x: x and 'Deadline' in str(x) if x else False)
            if not deadline_elem:
                # Try finding by content
                list_data_elems = box.find_all('p', class_='list-data')
                for elem in list_data_elems:
                    if 'Deadline' in elem.get_text():
                        deadline_elem = elem
                        break
            
            if deadline_elem:
                strong = deadline_elem.find('strong')
                if strong:
                    tender['Deadline'] = strong.get_text(strip=True)
            
            # Extract TOT Reference Number
            ref_elem = None
            list_data_elems = box.find_all('p', class_='list-data')
            for elem in list_data_elems:
                if 'TOT Reference' in elem.get_text() or 'TOT Ref' in elem.get_text():
                    ref_elem = elem
                    break
            
            if ref_elem:
                strong = ref_elem.find('strong')
                if strong:
                    tender['TOT_Reference_No'] = strong.get_text(strip=True)
            
            # Extract country from purchase-box
            country_elem = box.find('p', class_='purchase-box')
            if country_elem:
                strong = country_elem.find('strong')
                if strong:
                    tender['Country'] = strong.get_text(strip=True)
            
            # Get View Details link
            view_details = box.find('a', class_='listing-prod-view')
            if view_details and view_details.get('href'):
                tender['Detail_URL'] = view_details.get('href')
            
            # Skip invalid entries (template placeholders from website bugs)
            if tender.get('Title') and '{{' in tender.get('Title', ''):
                continue
            if tender.get('Detail_URL') and '{{' in tender.get('Detail_URL', ''):
                continue
            
            # Only add if we have valid data
            if tender.get('Title') and tender.get('Detail_URL'):
                # Validate URL format
                if tender['Detail_URL'].startswith('http'):
                    tenders.append(tender)
                
        except Exception as e:
            print(f"  Error extracting tender from listing box: {e}")
            continue
    
    return tenders


def extract_detail_page_info(url):
    """
    Visit detail page and extract additional information.
    The main content is in div.box_detail.
    """
    detail_info = {
        'Description': '',
        'Summary': '',
        'Notice_Type': '',
        'Document_Ref_No': '',
        'Financier': '',
        'Purchaser_Ownership': '',
        'Tender_Value': '',
        'Purchaser_Name': '',
        'Purchaser_Address': '',
        'Detail_Scraped': False
    }
    
    if not url:
        return detail_info
    
    soup = get_soup(url)
    if not soup:
        return detail_info
    
    try:
        # Extract from box_detail class
        box_detail = soup.find('div', class_='box_detail')
        
        if box_detail:
            # Get the full description text
            detail_info['Description'] = box_detail.get_text(' ', strip=True)
            detail_info['Detail_Scraped'] = True
            
            # Extract structured fields
            # Find all paragraphs with label: value format
            paragraphs = box_detail.find_all('p')
            
            for p in paragraphs:
                text = p.get_text(' ', strip=True)
                strong = p.find('strong', class_='strval')
                
                if not strong:
                    strong = p.find('strong')
                
                if strong:
                    value = strong.get_text(strip=True)
                    
                    # Skip login-protected values
                    if 'Login to see' in value:
                        value = '[Login Required]'
                    
                    # Map fields
                    if 'Country:' in text:
                        detail_info['Country_Detail'] = value
                    elif 'Summary:' in text:
                        detail_info['Summary'] = value
                    elif 'Deadline:' in text:
                        detail_info['Deadline_Detail'] = value
                    elif 'Notice Type:' in text:
                        detail_info['Notice_Type'] = value
                    elif 'TOT Ref' in text:
                        detail_info['TOT_Reference_Detail'] = value
                    elif 'Document Ref' in text:
                        detail_info['Document_Ref_No'] = value
                    elif 'Financier:' in text:
                        detail_info['Financier'] = value
                    elif 'Purchaser Ownership:' in text:
                        detail_info['Purchaser_Ownership'] = value
                    elif 'Tender Value:' in text:
                        detail_info['Tender_Value'] = value
                    elif 'Name:' in text and 'Purchase' not in text:
                        detail_info['Purchaser_Name'] = value
                    elif 'Address:' in text:
                        detail_info['Purchaser_Address'] = value
            
            # Extract the main description paragraph (first paragraph in desc-box-mobi)
            desc_box = box_detail.find('div', class_='desc-box-mobi')
            if desc_box:
                first_p = desc_box.find('p', class_='purchase-box')
                if first_p:
                    # Get text without the registration link
                    desc_text = first_p.get_text(' ', strip=True)
                    desc_text = re.sub(r'Registering\s+on the site\.?', '', desc_text)
                    # Clean up extra whitespace
                    desc_text = re.sub(r'\s+', ' ', desc_text)
                    detail_info['Description'] = desc_text.strip()
            
            # If description is still the full box_detail text, clean it up
            if detail_info['Description'] and len(detail_info['Description']) > 500:
                # Keep just the first paragraph (main description)
                desc_text = detail_info['Description']
                # Remove "Browse More" section and everything after
                desc_text = re.sub(r'Browse More.*$', '', desc_text, flags=re.DOTALL)
                # Remove "Documents Tender Notice" section
                desc_text = re.sub(r'Documents\s+Tender Notice.*$', '', desc_text, flags=re.DOTALL)
                # Clean up whitespace
                desc_text = re.sub(r'\s+', ' ', desc_text)
                detail_info['Description'] = desc_text.strip()
                
    except Exception as e:
        print(f"  Error extracting detail page info from {url}: {e}")
    
    return detail_info


def get_next_page_url(soup, current_url, page_num):
    """
    Find the URL for the next page.
    Note: The current site doesn't seem to have working pagination for Pakistan tenders.
    This function is kept for potential future use or different country pages.
    """
    try:
        # Try common pagination patterns
        next_link = soup.find('a', class_=re.compile(r'next', re.I))
        if not next_link:
            next_link = soup.find('a', string=re.compile(r'Next|›|»'))
        if not next_link:
            next_link = soup.find('a', rel='next')
        
        if next_link and next_link.get('href'):
            href = next_link['href']
            if href and href != current_url and href != '#':
                if href.startswith('http'):
                    return href
                elif href.startswith('/'):
                    return f"https://www.tendersontime.com{href}"
        
        return None
    except Exception as e:
        print(f"  Error finding next page: {e}")
        return None


def scrape_tenders():
    """Main function to scrape all tenders."""
    all_tenders = []
    current_url = BASE_URL
    page_num = 1
    total_available = 0
    
    print("=" * 70)
    print(f"Starting Pakistan Tenders Scraper at {datetime.now()}")
    print(f"Base URL: {BASE_URL}")
    print(f"Max records to scrape: {MAX_RECORDS if MAX_RECORDS else 'All available'}")
    print("=" * 70)
    
    while current_url:
        print(f"\n[Page {page_num}] Scraping: {current_url}")
        
        soup = get_soup(current_url)
        if not soup:
            print(f"  Failed to fetch page {page_num}, stopping.")
            break
        
        # Parse listings
        page_tenders = parse_listing_page(soup)
        
        if not page_tenders:
            print(f"  No tenders found on page {page_num}, stopping.")
            break
        
        print(f"  Found {len(page_tenders)} tenders on this page")
        total_available += len(page_tenders)
        
        # Process each tender - visit detail page
        for i, tender in enumerate(page_tenders):
            if MAX_RECORDS and len(all_tenders) >= MAX_RECORDS:
                print(f"\n  Reached maximum records limit ({MAX_RECORDS})")
                break
            
            title_preview = tender.get('Title', 'Unknown')[:45]
            print(f"  [{len(all_tenders) + 1}] Processing: {title_preview}...")
            
            # Get detailed information from detail page
            if tender.get('Detail_URL'):
                time.sleep(DELAY_BETWEEN_REQUESTS)
                detail_info = extract_detail_page_info(tender['Detail_URL'])
                tender.update(detail_info)
            
            all_tenders.append(tender)
        
        # Check if we've reached max records
        if MAX_RECORDS and len(all_tenders) >= MAX_RECORDS:
            break
        
        # Try to get next page (Note: Currently pagination doesn't work on this site)
        next_url = get_next_page_url(soup, current_url, page_num)
        if next_url and next_url != current_url:
            current_url = next_url
            page_num += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)
        else:
            print("\n  No more pages available.")
            break
    
    print("\n" + "=" * 70)
    print(f"Scraping completed at {datetime.now()}")
    print(f"Total tenders scraped: {len(all_tenders)}")
    print(f"Total records available on website: {total_available}")
    print("=" * 70)
    
    return all_tenders, total_available


def save_to_csv(tenders, filename=OUTPUT_CSV):
    """Save tenders to CSV file with organized columns."""
    if not tenders:
        print("No tenders to save.")
        return None
    
    df = pd.DataFrame(tenders)
    
    # Define column order for better readability
    priority_columns = [
        'Title',
        'TOT_Reference_No',
        'Country',
        'Deadline',
        'Notice_Type',
        'Financier',
        'Purchaser_Ownership',
        'Tender_Value',
        'Description',
        'Detail_URL',
        'Detail_Scraped'
    ]
    
    # Columns to exclude from output
    columns_to_remove = [
        'Document_Ref_No', 'Purchaser_Name', 'Purchaser_Address', 'Summary',
        'Detail_Scraped', 'Country_Detail', 'Deadline_Detail', 'TOT_Reference_Detail'
    ]
    for col in columns_to_remove:
        if col in df.columns:
            df = df.drop(columns=[col])
    
    # Get all columns and order them
    all_columns = list(df.columns)
    ordered_columns = [col for col in priority_columns if col in all_columns]
    remaining_columns = [col for col in all_columns if col not in ordered_columns]
    final_columns = ordered_columns + remaining_columns
    
    df = df[final_columns]
    
    # Clean up description - truncate if too long for display
    if 'Description' in df.columns:
        df['Description'] = df['Description'].apply(
            lambda x: x[:5000] if isinstance(x, str) and len(x) > 5000 else x
        )
    
    # Save to CSV
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"\nSaved {len(tenders)} tenders to {filename}")
    
    return df


def print_summary(df, total_available):
    """Print a summary of the scraped data."""
    if df is None:
        return
    
    print("\n" + "=" * 70)
    print("SCRAPING SUMMARY")
    print("=" * 70)
    print(f"Total records scraped: {len(df)}")
    print(f"Total records available on website: {total_available}")
    print(f"\nColumns in CSV ({len(df.columns)}):")
    for i, col in enumerate(df.columns, 1):
        non_null = df[col].notna().sum()
        print(f"  {i:2}. {col}: {non_null} non-null values")
    
    print("\n" + "-" * 70)
    print("Sample Data (First 3 records):")
    print("-" * 70)
    for idx, row in df.head(3).iterrows():
        print(f"\nRecord {idx + 1}:")
        print(f"  Title: {row.get('Title', 'N/A')[:60]}")
        print(f"  TOT Ref: {row.get('TOT_Reference_No', 'N/A')}")
        print(f"  Deadline: {row.get('Deadline', 'N/A')}")
        print(f"  Description: {str(row.get('Description', 'N/A'))[:100]}...")


def main():
    """Main entry point."""
    print("\n" + "=" * 70)
    print("PAKISTAN TENDERS SCRAPER")
    print("Website: https://www.tendersontime.com/pakistan-tenders/")
    print("=" * 70)
    
    # Scrape tenders
    tenders, total_available = scrape_tenders()
    
    # Save to CSV
    df = save_to_csv(tenders)
    
    # Print summary
    print_summary(df, total_available)
    
    print("\n" + "=" * 70)
    print("SCRAPER CONFIGURATION")
    print("=" * 70)
    print(f"MAX_RECORDS: {MAX_RECORDS}")
    print(f"DELAY_BETWEEN_REQUESTS: {DELAY_BETWEEN_REQUESTS} seconds")
    print(f"OUTPUT_CSV: {OUTPUT_CSV}")
    print("\nTo change settings, modify the configuration variables at the top of this script.")
    print("=" * 70)
    
    return tenders


if __name__ == "__main__":
    main()
