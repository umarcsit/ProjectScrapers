#!/usr/bin/env python3
"""
Scraper for Punjab eProcurement Portal - Active Tenders
Source: https://eproc.punjab.gov.pk/ActiveTenders.aspx

This scraper extracts tender information from the main listing page,
visits detail pages for each tender, and extracts PDF content where available.
"""

import os
import re
import io
import csv
import time
import logging
import requests
import urllib3
from urllib.parse import urljoin, urlparse
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd

# Suppress SSL warnings for sites with certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================
BASE_URL = "https://eproc.punjab.gov.pk"
ACTIVE_TENDERS_URL = f"{BASE_URL}/ActiveTenders.aspx"
OUTPUT_CSV = "eproc_punjab_gov_pk.csv"

# Maximum records to scrape (set to None for all records)
MAX_RECORDS = None  # Change this to limit records, e.g., MAX_RECORDS = 100

# Request settings
REQUEST_TIMEOUT = 60
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds
DELAY_BETWEEN_REQUESTS = 2  # seconds to be polite to the server

# Headers to mimic browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}


class EProcPunjabScraper:
    """Scraper for Punjab eProcurement Portal Active Tenders."""
    
    def __init__(self, max_records=None):
        """
        Initialize the scraper.
        
        Args:
            max_records: Maximum number of records to scrape. None for all.
        """
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.verify = False  # Handle SSL certificate issues
        self.max_records = max_records
        self.total_records_available = 0
        self.scraped_records = 0
        self.tenders = []
        
        # ASP.NET form state
        self.viewstate = ""
        self.viewstategenerator = ""
        self.eventvalidation = ""
        
    def _make_request(self, url, method='GET', data=None, retries=RETRY_ATTEMPTS):
        """
        Make HTTP request with retry logic.
        
        Args:
            url: URL to request
            method: HTTP method (GET or POST)
            data: POST data if applicable
            retries: Number of retry attempts
            
        Returns:
            Response object or None if failed
        """
        for attempt in range(retries):
            try:
                if method == 'GET':
                    response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                else:
                    response = self.session.post(url, data=data, timeout=REQUEST_TIMEOUT)
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    
        logger.error(f"Failed to fetch {url} after {retries} attempts")
        return None
    
    def _extract_asp_state(self, soup):
        """Extract ASP.NET form state variables."""
        viewstate = soup.find('input', {'id': '__VIEWSTATE'})
        viewstategenerator = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
        eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})
        eventtarget = soup.find('input', {'id': '__EVENTTARGET'})
        eventargument = soup.find('input', {'id': '__EVENTARGUMENT'})
        
        self.viewstate = viewstate.get('value', '') if viewstate else ''
        self.viewstategenerator = viewstategenerator.get('value', '') if viewstategenerator else ''
        self.eventvalidation = eventvalidation.get('value', '') if eventvalidation else ''
        self.eventtarget = eventtarget.get('value', '') if eventtarget else ''
        self.eventargument = eventargument.get('value', '') if eventargument else ''
        
    def _extract_pdf_text(self, pdf_url):
        """
        Download PDF and extract text content.
        
        Args:
            pdf_url: URL of the PDF file
            
        Returns:
            Extracted text or empty string if failed
        """
        if not pdf_url:
            return ""
            
        try:
            # Try pdfplumber first (better text extraction)
            try:
                import pdfplumber
                
                response = self._make_request(pdf_url)
                if not response:
                    return ""
                    
                pdf_bytes = io.BytesIO(response.content)
                text_parts = []
                
                with pdfplumber.open(pdf_bytes) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                            
                return "\n".join(text_parts).strip()
                
            except ImportError:
                # Fallback to PyPDF2
                from PyPDF2 import PdfReader
                
                response = self._make_request(pdf_url)
                if not response:
                    return ""
                    
                pdf_bytes = io.BytesIO(response.content)
                reader = PdfReader(pdf_bytes)
                text_parts = []
                
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                        
                return "\n".join(text_parts).strip()
                
        except Exception as e:
            logger.warning(f"Failed to extract PDF text from {pdf_url}: {e}")
            return ""
    
    def _extract_detail_page(self, detail_url):
        """
        Extract additional information from tender detail page.
        
        Args:
            detail_url: URL of the tender detail page
            
        Returns:
            Dictionary with extracted details
        """
        details = {
            'detail_description': '',
            'detail_organization': '',
            'detail_tender_type': '',
            'detail_category': '',
            'detail_estimated_cost': '',
            'detail_earnest_money': '',
            'detail_tender_fee': '',
            'detail_submission_deadline': '',
            'detail_opening_date': '',
            'detail_validity_period': '',
            'detail_contact_person': '',
            'detail_contact_email': '',
            'detail_contact_phone': '',
            'detail_address': '',
            'detail_special_instructions': '',
            'detail_eligibility_criteria': '',
            'detail_technical_specifications': '',
            'detail_raw_content': '',
        }
        
        if not detail_url:
            return details
            
        try:
            response = self._make_request(detail_url)
            if not response:
                return details
                
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Extract all text content from the page
            main_content = soup.find('div', {'class': ['content', 'main-content', 'tender-detail']})
            if not main_content:
                main_content = soup.find('form') or soup.body
                
            if main_content:
                details['detail_raw_content'] = main_content.get_text(separator='\n', strip=True)
            
            # Try to extract specific fields from tables
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        # Map common labels to our fields
                        label_mappings = {
                            'description': 'detail_description',
                            'tender description': 'detail_description',
                            'organization': 'detail_organization',
                            'department': 'detail_organization',
                            'procuring agency': 'detail_organization',
                            'tender type': 'detail_tender_type',
                            'procurement type': 'detail_tender_type',
                            'category': 'detail_category',
                            'estimated cost': 'detail_estimated_cost',
                            'estimated value': 'detail_estimated_cost',
                            'earnest money': 'detail_earnest_money',
                            'bid security': 'detail_earnest_money',
                            'tender fee': 'detail_tender_fee',
                            'document fee': 'detail_tender_fee',
                            'submission deadline': 'detail_submission_deadline',
                            'closing date': 'detail_submission_deadline',
                            'last date': 'detail_submission_deadline',
                            'opening date': 'detail_opening_date',
                            'bid opening': 'detail_opening_date',
                            'validity': 'detail_validity_period',
                            'valid till': 'detail_validity_period',
                            'contact person': 'detail_contact_person',
                            'contact name': 'detail_contact_person',
                            'email': 'detail_contact_email',
                            'phone': 'detail_contact_phone',
                            'telephone': 'detail_contact_phone',
                            'mobile': 'detail_contact_phone',
                            'address': 'detail_address',
                            'special instructions': 'detail_special_instructions',
                            'remarks': 'detail_special_instructions',
                            'eligibility': 'detail_eligibility_criteria',
                            'eligibility criteria': 'detail_eligibility_criteria',
                            'pre-qualification': 'detail_eligibility_criteria',
                            'specifications': 'detail_technical_specifications',
                            'technical specifications': 'detail_technical_specifications',
                        }
                        
                        for key, field in label_mappings.items():
                            if key in label:
                                details[field] = value
                                break
            
            # Extract description from common containers
            desc_containers = soup.find_all(['div', 'p', 'span'], 
                                           class_=re.compile(r'description|content|detail', re.I))
            for container in desc_containers:
                text = container.get_text(strip=True)
                if len(text) > len(details['detail_description']):
                    details['detail_description'] = text
                    
        except Exception as e:
            logger.warning(f"Failed to extract detail page {detail_url}: {e}")
            
        return details
    
    def _parse_tender_row(self, row, row_index):
        """
        Parse a single tender row from the main table.
        
        Args:
            row: BeautifulSoup table row element
            row_index: Index of the row
            
        Returns:
            Dictionary with tender data or None if parsing failed
        """
        cells = row.find_all('td')
        if not cells or len(cells) < 3:
            return None
            
        tender = {
            'sr_no': '',
            'procurement_name': '',
            'procurement_name_link': '',
            'tender_notice': '',
            'tender_notice_pdf_link': '',
            'bidding_document': '',
            'bidding_document_pdf_link': '',
            'organization': '',
            'tender_ref_no': '',
            'published_date': '',
            'closing_date': '',
            'opening_date': '',
            'tender_value': '',
            'tender_status': '',
            'description': '',
            'tender_notice_pdf_text': '',
            'bidding_document_pdf_text': '',
        }
        
        try:
            # Extract data based on common column structures
            # Column indices may vary - try to detect by content
            
            for idx, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True)
                
                # Check for serial number (usually first column, numeric)
                if idx == 0 and cell_text.isdigit():
                    tender['sr_no'] = cell_text
                    continue
                    
                # Check for links in the cell
                links = cell.find_all('a')
                
                for link in links:
                    href = link.get('href', '')
                    link_text = link.get_text(strip=True)
                    
                    # Full URL
                    full_url = urljoin(BASE_URL, href) if href else ''
                    
                    # Detect link type by text or href
                    link_text_lower = link_text.lower()
                    href_lower = href.lower()
                    
                    if 'view' in link_text_lower or 'detail' in link_text_lower:
                        tender['procurement_name_link'] = full_url
                        tender['procurement_name'] = cell_text.replace(link_text, '').strip() or link_text
                    elif href_lower.endswith('.pdf') or 'pdf' in link_text_lower:
                        if 'notice' in link_text_lower or 'notice' in cell_text.lower():
                            tender['tender_notice_pdf_link'] = full_url
                            tender['tender_notice'] = link_text
                        elif 'document' in link_text_lower or 'bidding' in cell_text.lower():
                            tender['bidding_document_pdf_link'] = full_url
                            tender['bidding_document'] = link_text
                        elif not tender['tender_notice_pdf_link']:
                            tender['tender_notice_pdf_link'] = full_url
                            tender['tender_notice'] = link_text
                        else:
                            tender['bidding_document_pdf_link'] = full_url
                            tender['bidding_document'] = link_text
                
                # If no links found, try to detect column by position or content
                if not links:
                    cell_text_lower = cell_text.lower()
                    
                    # Try to identify columns by content patterns
                    if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', cell_text):
                        # Date pattern
                        if not tender['published_date']:
                            tender['published_date'] = cell_text
                        elif not tender['closing_date']:
                            tender['closing_date'] = cell_text
                        elif not tender['opening_date']:
                            tender['opening_date'] = cell_text
                    elif re.match(r'[A-Z]{2,}[-/]\d+', cell_text, re.I):
                        # Reference number pattern
                        tender['tender_ref_no'] = cell_text
                    elif 'rs' in cell_text_lower or re.match(r'[\d,]+\.?\d*', cell_text):
                        # Monetary value
                        if not tender['tender_value']:
                            tender['tender_value'] = cell_text
                    elif not tender['organization'] and len(cell_text) > 5:
                        tender['organization'] = cell_text
                        
            # If procurement name is still empty, use first non-empty cell after sr_no
            if not tender['procurement_name']:
                for idx, cell in enumerate(cells[1:], 1):
                    text = cell.get_text(strip=True)
                    if text and len(text) > 3:
                        tender['procurement_name'] = text
                        # Check for link
                        link = cell.find('a')
                        if link:
                            tender['procurement_name_link'] = urljoin(BASE_URL, link.get('href', ''))
                        break
                        
        except Exception as e:
            logger.warning(f"Error parsing row {row_index}: {e}")
            return None
            
        return tender
    
    def _get_total_records(self, soup):
        """
        Extract total number of records from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Total record count or 0 if not found
        """
        # Look for common patterns like "Showing 1-20 of 150 records"
        text = soup.get_text()
        
        patterns = [
            r'of\s+(\d+)\s+records?',
            r'total\s*:?\s*(\d+)',
            r'(\d+)\s+tenders?\s+found',
            r'showing\s+\d+\s*-\s*\d+\s+of\s+(\d+)',
            r'page\s+\d+\s+of\s+\d+\s*\((\d+)\s+records?\)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return int(match.group(1))
                
        # Count rows in the main table as fallback
        table = soup.find('table', {'id': re.compile(r'grid|tender|list', re.I)})
        if table:
            rows = table.find_all('tr')
            # Subtract header row
            return max(0, len(rows) - 1)
            
        return 0
    
    def _get_next_page_data(self, soup, current_page):
        """
        Prepare POST data for next page request (ASP.NET pagination).
        
        Args:
            soup: BeautifulSoup object of current page
            current_page: Current page number
            
        Returns:
            POST data dictionary or None if no more pages
        """
        # Look for pagination controls
        pager = soup.find('tr', {'class': re.compile(r'pager|pagination', re.I)})
        if not pager:
            pager = soup.find('div', {'class': re.compile(r'pager|pagination', re.I)})
            
        if not pager:
            return None
            
        # Find next page link
        next_link = pager.find('a', text=re.compile(r'next|>|»|\d+', re.I))
        if not next_link:
            # Try finding link with page number greater than current
            links = pager.find_all('a')
            for link in links:
                try:
                    page_num = int(link.get_text(strip=True))
                    if page_num > current_page:
                        next_link = link
                        break
                except ValueError:
                    continue
                    
        if not next_link:
            return None
            
        # Extract ASP.NET postback parameters
        href = next_link.get('href', '')
        
        # Parse __doPostBack('ctl00$ContentPlaceHolder1$gvTenders','Page$2')
        postback_match = re.search(r"__doPostBack\('([^']+)',\s*'([^']+)'\)", href)
        
        if postback_match:
            event_target = postback_match.group(1)
            event_argument = postback_match.group(2)
        else:
            event_target = next_link.get('name', '')
            event_argument = ''
            
        # Build POST data
        post_data = {
            '__EVENTTARGET': event_target,
            '__EVENTARGUMENT': event_argument,
            '__VIEWSTATE': self.viewstate,
            '__VIEWSTATEGENERATOR': self.viewstategenerator,
            '__EVENTVALIDATION': self.eventvalidation,
        }
        
        return post_data
    
    def scrape_main_page(self):
        """
        Scrape the main active tenders listing page.
        
        Returns:
            List of tender dictionaries
        """
        logger.info(f"Starting to scrape {ACTIVE_TENDERS_URL}")
        
        # Fetch the first page
        response = self._make_request(ACTIVE_TENDERS_URL)
        if not response:
            logger.error("Failed to fetch main page")
            return []
            
        soup = BeautifulSoup(response.content, 'lxml')
        self._extract_asp_state(soup)
        
        # Get total records
        self.total_records_available = self._get_total_records(soup)
        logger.info(f"Total records available: {self.total_records_available}")
        
        current_page = 1
        all_tenders = []
        
        while True:
            logger.info(f"Processing page {current_page}")
            
            # Find the main tender table
            table = soup.find('table', {'id': re.compile(r'grid|tender|list', re.I)})
            if not table:
                # Try finding by class or just the largest table
                tables = soup.find_all('table')
                if tables:
                    table = max(tables, key=lambda t: len(t.find_all('tr')))
                    
            if not table:
                logger.warning(f"No tender table found on page {current_page}")
                break
                
            # Get all data rows (skip header)
            rows = table.find_all('tr')
            data_rows = [r for r in rows if r.find('td')]
            
            logger.info(f"Found {len(data_rows)} tender rows on page {current_page}")
            
            for idx, row in enumerate(data_rows):
                if self.max_records and len(all_tenders) >= self.max_records:
                    logger.info(f"Reached max records limit: {self.max_records}")
                    break
                    
                tender = self._parse_tender_row(row, idx)
                if tender:
                    all_tenders.append(tender)
                    self.scraped_records += 1
                    
            # Check if we've reached max records
            if self.max_records and len(all_tenders) >= self.max_records:
                break
                
            # Try to get next page
            next_page_data = self._get_next_page_data(soup, current_page)
            if not next_page_data:
                logger.info("No more pages to process")
                break
                
            # Fetch next page
            time.sleep(DELAY_BETWEEN_REQUESTS)
            response = self._make_request(ACTIVE_TENDERS_URL, method='POST', data=next_page_data)
            if not response:
                logger.error(f"Failed to fetch page {current_page + 1}")
                break
                
            soup = BeautifulSoup(response.content, 'lxml')
            self._extract_asp_state(soup)
            current_page += 1
            
        return all_tenders
    
    def enrich_tender_data(self, tenders):
        """
        Enrich tender data by visiting detail pages and extracting PDFs.
        
        Args:
            tenders: List of tender dictionaries
            
        Returns:
            Enriched tender list
        """
        total = len(tenders)
        
        for idx, tender in enumerate(tenders):
            logger.info(f"Enriching tender {idx + 1}/{total}: {tender.get('procurement_name', 'Unknown')[:50]}...")
            
            # Visit detail page
            if tender.get('procurement_name_link'):
                logger.info(f"  Fetching detail page...")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                details = self._extract_detail_page(tender['procurement_name_link'])
                tender.update(details)
                
            # Extract tender notice PDF text
            if tender.get('tender_notice_pdf_link'):
                logger.info(f"  Extracting tender notice PDF...")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                tender['tender_notice_pdf_text'] = self._extract_pdf_text(tender['tender_notice_pdf_link'])
                
            # Extract bidding document PDF text
            if tender.get('bidding_document_pdf_link'):
                logger.info(f"  Extracting bidding document PDF...")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                tender['bidding_document_pdf_text'] = self._extract_pdf_text(tender['bidding_document_pdf_link'])
                
            # Compile final description
            description_parts = []
            
            if tender.get('detail_description'):
                description_parts.append(f"Detail Description:\n{tender['detail_description']}")
                
            if tender.get('tender_notice_pdf_text'):
                description_parts.append(f"Tender Notice Content:\n{tender['tender_notice_pdf_text']}")
                
            if tender.get('bidding_document_pdf_text'):
                description_parts.append(f"Bidding Document Content:\n{tender['bidding_document_pdf_text']}")
                
            if tender.get('detail_raw_content') and not description_parts:
                description_parts.append(f"Page Content:\n{tender['detail_raw_content']}")
                
            tender['description'] = "\n\n---\n\n".join(description_parts)
            
        return tenders
    
    def save_to_csv(self, tenders, filename=OUTPUT_CSV):
        """
        Save tenders to CSV file.
        
        Args:
            tenders: List of tender dictionaries
            filename: Output CSV filename
        """
        if not tenders:
            logger.warning("No tenders to save")
            return
            
        # Define column order for better readability
        column_order = [
            'sr_no',
            'procurement_name',
            'procurement_name_link',
            'organization',
            'tender_ref_no',
            'tender_notice',
            'tender_notice_pdf_link',
            'bidding_document',
            'bidding_document_pdf_link',
            'published_date',
            'closing_date',
            'opening_date',
            'tender_value',
            'tender_status',
            'detail_organization',
            'detail_tender_type',
            'detail_category',
            'detail_estimated_cost',
            'detail_earnest_money',
            'detail_tender_fee',
            'detail_submission_deadline',
            'detail_opening_date',
            'detail_validity_period',
            'detail_contact_person',
            'detail_contact_email',
            'detail_contact_phone',
            'detail_address',
            'detail_eligibility_criteria',
            'detail_technical_specifications',
            'detail_special_instructions',
            'description',
            'tender_notice_pdf_text',
            'bidding_document_pdf_text',
            'detail_description',
            'detail_raw_content',
        ]
        
        # Get all unique columns from data
        all_columns = set()
        for tender in tenders:
            all_columns.update(tender.keys())
            
        # Order columns: defined order first, then any additional columns
        ordered_columns = [c for c in column_order if c in all_columns]
        additional_columns = sorted(all_columns - set(column_order))
        final_columns = ordered_columns + additional_columns
        
        # Create DataFrame and save
        df = pd.DataFrame(tenders, columns=final_columns)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        logger.info(f"Saved {len(tenders)} tenders to {filename}")
        logger.info(f"CSV columns: {len(final_columns)}")
        
    def run(self):
        """
        Run the complete scraping process.
        
        Returns:
            Tuple of (tenders list, total_available, scraped_count)
        """
        logger.info("=" * 60)
        logger.info("Punjab eProcurement Portal Scraper")
        logger.info(f"URL: {ACTIVE_TENDERS_URL}")
        logger.info(f"Max Records: {self.max_records or 'All'}")
        logger.info("=" * 60)
        
        # Scrape main page
        tenders = self.scrape_main_page()
        
        if not tenders:
            logger.warning("No tenders found on main page")
            return [], self.total_records_available, 0
            
        logger.info(f"Scraped {len(tenders)} tenders from main listing")
        
        # Enrich with detail page and PDF content
        tenders = self.enrich_tender_data(tenders)
        
        # Save to CSV
        self.save_to_csv(tenders)
        
        # Print summary
        logger.info("=" * 60)
        logger.info("SCRAPING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Records Available: {self.total_records_available}")
        logger.info(f"Records Scraped: {len(tenders)}")
        logger.info(f"Output File: {OUTPUT_CSV}")
        logger.info("=" * 60)
        
        return tenders, self.total_records_available, len(tenders)


def main():
    """Main entry point."""
    # Create scraper with optional max records limit
    scraper = EProcPunjabScraper(max_records=MAX_RECORDS)
    
    try:
        tenders, total_available, scraped_count = scraper.run()
        
        print("\n" + "=" * 60)
        print("FINAL REPORT")
        print("=" * 60)
        print(f"Total Records Available on Website: {total_available}")
        print(f"Total Records Scraped: {scraped_count}")
        print(f"Output CSV File: {OUTPUT_CSV}")
        
        if tenders:
            print(f"\nSample of scraped data:")
            for i, tender in enumerate(tenders[:3], 1):
                print(f"\n{i}. {tender.get('procurement_name', 'N/A')[:60]}...")
                print(f"   Organization: {tender.get('organization', 'N/A')[:40]}")
                print(f"   Detail Link: {tender.get('procurement_name_link', 'N/A')[:50]}")
                print(f"   Description Length: {len(tender.get('description', ''))}")
                
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise


if __name__ == "__main__":
    main()
