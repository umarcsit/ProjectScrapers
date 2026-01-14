#!/usr/bin/env python3
"""
Scraper for Punjab eProcurement Portal - Active Tenders
Source: https://eproc.punjab.gov.pk/ActiveTenders.aspx

This scraper extracts tender information from the main listing page,
visits detail pages for each tender (where available), and extracts PDF content.

Columns on the website:
- Procurement Title (type: Tender Notice, Request for Proposal, etc.)
- Procurement Name (with optional "View Tender Detail" link)
- Type (Goods, Services, Work)
- Publish Date
- Close Date
- Department
- Status
- Tender Notice (PDF link)
- Bidding Document (PDF link)
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

# Table and pagination identifiers (from website analysis)
TABLE_ID = 'ctl00_ContentPlaceHolderSRIS_rdgrdManageTender_ctl00'
PAGINATION_TARGET = 'ctl00$ContentPlaceHolderSRIS$rdgrdManageTender$ctl00$ctl03$ctl01$ctl'


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
        self.total_pages = 0
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
        
        self.viewstate = viewstate.get('value', '') if viewstate else ''
        self.viewstategenerator = viewstategenerator.get('value', '') if viewstategenerator else ''
        self.eventvalidation = eventvalidation.get('value', '') if eventvalidation else ''
        
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
                
                logger.debug(f"Downloading PDF: {pdf_url}")
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
            detail_url: URL of the tender detail page (ActiveTendersDetail.aspx?id=xxx)
            
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
            logger.info(f"Fetching detail page: {detail_url}")
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
            
            # Extract from labeled spans (common in ASP.NET)
            for span in soup.find_all('span', id=True):
                span_id = span.get('id', '').lower()
                text = span.get_text(strip=True)
                if not text:
                    continue
                    
                if 'description' in span_id:
                    details['detail_description'] = text
                elif 'organization' in span_id or 'department' in span_id or 'agency' in span_id:
                    details['detail_organization'] = text
                elif 'type' in span_id and 'tender' in span_id:
                    details['detail_tender_type'] = text
                elif 'category' in span_id:
                    details['detail_category'] = text
                elif 'cost' in span_id or 'value' in span_id or 'amount' in span_id:
                    details['detail_estimated_cost'] = text
                elif 'earnest' in span_id or 'security' in span_id:
                    details['detail_earnest_money'] = text
                elif 'fee' in span_id:
                    details['detail_tender_fee'] = text
                elif 'deadline' in span_id or 'closing' in span_id or 'submission' in span_id:
                    details['detail_submission_deadline'] = text
                elif 'opening' in span_id:
                    details['detail_opening_date'] = text
                elif 'validity' in span_id:
                    details['detail_validity_period'] = text
                elif 'contact' in span_id and 'person' in span_id:
                    details['detail_contact_person'] = text
                elif 'email' in span_id:
                    details['detail_contact_email'] = text
                elif 'phone' in span_id or 'mobile' in span_id or 'tel' in span_id:
                    details['detail_contact_phone'] = text
                elif 'address' in span_id:
                    details['detail_address'] = text
                elif 'instruction' in span_id or 'remark' in span_id:
                    details['detail_special_instructions'] = text
                elif 'eligibility' in span_id or 'qualification' in span_id:
                    details['detail_eligibility_criteria'] = text
                elif 'specification' in span_id:
                    details['detail_technical_specifications'] = text
            
            # Try to extract from tables
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        # Map common labels
                        if 'description' in label and not details['detail_description']:
                            details['detail_description'] = value
                        elif ('organization' in label or 'department' in label) and not details['detail_organization']:
                            details['detail_organization'] = value
                        elif 'type' in label and not details['detail_tender_type']:
                            details['detail_tender_type'] = value
                        elif 'estimated' in label or 'cost' in label:
                            details['detail_estimated_cost'] = value
                        elif 'earnest' in label or 'bid security' in label:
                            details['detail_earnest_money'] = value
                        elif 'fee' in label:
                            details['detail_tender_fee'] = value
                        elif 'deadline' in label or 'closing' in label or 'last date' in label:
                            details['detail_submission_deadline'] = value
                        elif 'opening' in label:
                            details['detail_opening_date'] = value
                        elif 'validity' in label:
                            details['detail_validity_period'] = value
                        elif 'contact' in label:
                            details['detail_contact_person'] = value
                        elif 'email' in label:
                            details['detail_contact_email'] = value
                        elif 'phone' in label or 'mobile' in label:
                            details['detail_contact_phone'] = value
                        elif 'address' in label:
                            details['detail_address'] = value
                    
        except Exception as e:
            logger.warning(f"Failed to extract detail page {detail_url}: {e}")
            
        return details
    
    def _parse_tender_row(self, row, row_index):
        """
        Parse a single tender row from the main table.
        
        Expected columns:
        0: Procurement Title (type of notice)
        1: Procurement Name (may contain View Tender Detail link)
        2: Type (Goods/Services/Work)
        3: Publish Date
        4: Close Date
        5: Department
        6: Status
        7: Tender Notice (PDF link)
        8: Bidding Document (PDF link)
        
        Args:
            row: BeautifulSoup table row element
            row_index: Index of the row
            
        Returns:
            Dictionary with tender data or None if parsing failed
        """
        cells = row.find_all('td')
        if not cells or len(cells) < 9:
            return None
            
        tender = {
            'sr_no': row_index + 1,
            'procurement_title': '',  # Type of notice (Tender Notice, RFP, etc.)
            'procurement_name': '',   # Actual tender name/description
            'detail_page_link': '',   # View Tender Detail link if available
            'type': '',               # Goods/Services/Work
            'publish_date': '',
            'close_date': '',
            'department': '',
            'status': '',
            'tender_notice_link': '',
            'bidding_document_link': '',
            'description': '',
            'tender_notice_pdf_text': '',
            'bidding_document_pdf_text': '',
        }
        
        try:
            # Column 0: Procurement Title (type of notice)
            tender['procurement_title'] = cells[0].get_text(strip=True)
            
            # Column 1: Procurement Name (may contain View Tender Detail link)
            cell_1 = cells[1]
            tender['procurement_name'] = cell_1.get_text(strip=True)
            
            # Check for "View Tender Detail" link
            detail_link = cell_1.find('a', href=re.compile(r'ActiveTendersDetail\.aspx', re.I))
            if detail_link:
                href = detail_link.get('href', '')
                tender['detail_page_link'] = urljoin(BASE_URL, href)
                # Remove link text from procurement name
                link_text = detail_link.get_text(strip=True)
                tender['procurement_name'] = tender['procurement_name'].replace(link_text, '').strip()
                tender['procurement_name'] = re.sub(r'\s*\(\s*\)\s*$', '', tender['procurement_name'])
            
            # Column 2: Type
            tender['type'] = cells[2].get_text(strip=True)
            
            # Column 3: Publish Date
            tender['publish_date'] = cells[3].get_text(strip=True)
            
            # Column 4: Close Date
            tender['close_date'] = cells[4].get_text(strip=True)
            
            # Column 5: Department
            tender['department'] = cells[5].get_text(strip=True)
            
            # Column 6: Status
            tender['status'] = cells[6].get_text(strip=True)
            
            # Column 7: Tender Notice PDF
            cell_7 = cells[7]
            pdf_link = cell_7.find('a', href=re.compile(r'\.pdf', re.I))
            if pdf_link:
                href = pdf_link.get('href', '')
                tender['tender_notice_link'] = urljoin(BASE_URL, href)
            
            # Column 8: Bidding Document PDF
            cell_8 = cells[8]
            pdf_link = cell_8.find('a', href=re.compile(r'\.pdf', re.I))
            if pdf_link:
                href = pdf_link.get('href', '')
                tender['bidding_document_link'] = urljoin(BASE_URL, href)
                
        except Exception as e:
            logger.warning(f"Error parsing row {row_index}: {e}")
            return None
            
        return tender
    
    def _get_total_records(self, soup):
        """
        Extract total number of records and pages from the page.
        
        Looks for pattern like "638 items in 7 pages"
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Tuple of (total_items, total_pages)
        """
        text = soup.get_text()
        
        # Pattern: "638 items in 7 pages"
        match = re.search(r'(\d+)\s*items?\s+in\s+(\d+)\s*pages?', text, re.I)
        if match:
            return int(match.group(1)), int(match.group(2))
            
        # Alternative patterns
        items_match = re.search(r'total\s*:?\s*(\d+)', text, re.I)
        pages_match = re.search(r'page\s+\d+\s+of\s+(\d+)', text, re.I)
        
        items = int(items_match.group(1)) if items_match else 0
        pages = int(pages_match.group(1)) if pages_match else 1
        
        return items, pages
    
    def _get_pagination_data(self, soup, page_number):
        """
        Prepare POST data for pagination request.
        
        The site uses ASP.NET with Telerik RadGrid pagination.
        
        Args:
            soup: BeautifulSoup object of current page
            page_number: Target page number (1-indexed)
            
        Returns:
            POST data dictionary or None if pagination not possible
        """
        # Find pagination div
        pager = soup.find('div', class_='rgWrap rgNumPart')
        if not pager:
            return None
            
        # Find the link for the target page
        page_links = pager.find_all('a')
        target_link = None
        
        for link in page_links:
            try:
                link_page = int(link.get_text(strip=True))
                if link_page == page_number:
                    target_link = link
                    break
            except ValueError:
                continue
        
        if not target_link:
            # Try "..." or next page buttons
            for link in page_links:
                href = link.get('href', '')
                if f"Page${page_number}" in href:
                    target_link = link
                    break
                    
        if not target_link:
            return None
            
        # Extract __doPostBack parameters
        href = target_link.get('href', '')
        postback_match = re.search(r"__doPostBack\('([^']+)',\s*'([^']+)'\)", href)
        
        if not postback_match:
            return None
            
        event_target = postback_match.group(1)
        event_argument = postback_match.group(2)
        
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
        Scrape the main active tenders listing page with pagination.
        
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
        
        # Get total records and pages
        self.total_records_available, self.total_pages = self._get_total_records(soup)
        logger.info(f"Total records available: {self.total_records_available}")
        logger.info(f"Total pages: {self.total_pages}")
        
        current_page = 1
        all_tenders = []
        
        while True:
            logger.info(f"Processing page {current_page}/{self.total_pages}")
            
            # Find the main tender table
            table = soup.find('table', {'id': TABLE_ID})
            if not table:
                # Fallback: find table with rgMasterTable class
                table = soup.find('table', class_='rgMasterTable')
                
            if not table:
                logger.warning(f"No tender table found on page {current_page}")
                break
                
            # Get all data rows (skip header, look for rgRow and rgAltRow classes)
            data_rows = table.find_all('tr', class_=['rgRow', 'rgAltRow'])
            
            logger.info(f"Found {len(data_rows)} tender rows on page {current_page}")
            
            for idx, row in enumerate(data_rows):
                if self.max_records and len(all_tenders) >= self.max_records:
                    logger.info(f"Reached max records limit: {self.max_records}")
                    break
                    
                tender = self._parse_tender_row(row, len(all_tenders))
                if tender:
                    all_tenders.append(tender)
                    self.scraped_records += 1
                    
            # Check if we've reached max records
            if self.max_records and len(all_tenders) >= self.max_records:
                break
                
            # Check if there are more pages
            if current_page >= self.total_pages:
                logger.info("Reached last page")
                break
                
            # Try to get next page
            next_page = current_page + 1
            next_page_data = self._get_pagination_data(soup, next_page)
            
            if not next_page_data:
                logger.info("No more pages available")
                break
                
            # Fetch next page
            time.sleep(DELAY_BETWEEN_REQUESTS)
            response = self._make_request(ACTIVE_TENDERS_URL, method='POST', data=next_page_data)
            if not response:
                logger.error(f"Failed to fetch page {next_page}")
                break
                
            soup = BeautifulSoup(response.content, 'lxml')
            self._extract_asp_state(soup)
            current_page = next_page
            
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
            
            # Visit detail page if available
            if tender.get('detail_page_link'):
                logger.info(f"  Fetching detail page...")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                details = self._extract_detail_page(tender['detail_page_link'])
                tender.update(details)
                
            # Extract tender notice PDF text
            if tender.get('tender_notice_link'):
                logger.info(f"  Extracting tender notice PDF...")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                tender['tender_notice_pdf_text'] = self._extract_pdf_text(tender['tender_notice_link'])
                
            # Extract bidding document PDF text
            if tender.get('bidding_document_link'):
                logger.info(f"  Extracting bidding document PDF...")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                tender['bidding_document_pdf_text'] = self._extract_pdf_text(tender['bidding_document_link'])
                
            # Compile final description from all sources
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
            # Main listing columns
            'sr_no',
            'procurement_title',
            'procurement_name',
            'type',
            'publish_date',
            'close_date',
            'department',
            'status',
            'tender_notice_link',
            'bidding_document_link',
            'detail_page_link',
            # Detail page columns
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
            # Description columns (combined and raw)
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
        logger.info(f"Total Pages: {self.total_pages}")
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
            print(f"\nSample of scraped data (first 3 records):")
            for i, tender in enumerate(tenders[:3], 1):
                print(f"\n{i}. [{tender.get('procurement_title', 'N/A')}] {tender.get('procurement_name', 'N/A')[:60]}...")
                print(f"   Type: {tender.get('type', 'N/A')}")
                print(f"   Department: {tender.get('department', 'N/A')[:50]}")
                print(f"   Published: {tender.get('publish_date', 'N/A')} | Closes: {tender.get('close_date', 'N/A')}")
                print(f"   Tender Notice PDF: {'Yes' if tender.get('tender_notice_link') else 'No'}")
                print(f"   Bidding Doc PDF: {'Yes' if tender.get('bidding_document_link') else 'No'}")
                print(f"   Detail Page: {'Yes' if tender.get('detail_page_link') else 'No'}")
                print(f"   Description Length: {len(tender.get('description', ''))}")
                
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise


if __name__ == "__main__":
    main()
