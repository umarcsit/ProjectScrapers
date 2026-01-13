#!/usr/bin/env python3
"""
PPRA Pakistan Active Tenders Scraper
Scrapes tender information from https://ppra.gov.pk/#/tenders/activetenders
Uses Playwright to handle dynamic SPA content
Extracts tender details including description from detail pages
Outputs to CSV file
"""

import csv
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from playwright.sync_api import sync_playwright, Page, Response

# Configuration
BASE_URL = "https://ppra.gov.pk"
TENDERS_URL = f"{BASE_URL}/#/tenders/activetenders"
OUTPUT_FILE = "ppra_active_tenders.csv"


class PPRAScraper:
    def __init__(self):
        self.tenders = []
        self.api_data = []
        
    def handle_response(self, response: Response):
        """Intercept API responses"""
        try:
            url = response.url
            if response.status == 200 and 'application/json' in response.headers.get('content-type', ''):
                if 'getallpublictenders' in url.lower():
                    try:
                        data = response.json()
                        if data.get('success') and data.get('data'):
                            records = data['data'].get('records', [])
                            if records:
                                self.api_data.extend(records)
                                print(f"[API: {len(records)} records]", end=' ')
                    except:
                        pass
        except:
            pass

    def extract_tenders_with_links(self, page: Page) -> List[Dict]:
        """Extract tenders and their detail page links"""
        tenders = []
        
        try:
            page.wait_for_selector('table tbody tr', timeout=15000)
            rows = page.query_selector_all('table tbody tr')
            
            for row in rows:
                try:
                    tender = {}
                    
                    # Get cells
                    cells = row.query_selector_all('td')
                    
                    # Find TS link for navigation
                    ts_link = row.query_selector('a[href*="activetenders"]')
                    if ts_link:
                        href = ts_link.get_attribute('href') or ''
                        text = ts_link.inner_text().strip()
                        if text.startswith('TS'):
                            tender['ts_no'] = text
                        # Extract path for detail page
                        match = re.search(r'activetenders/([^/?\s]+)', href)
                        if match:
                            tender['detail_path'] = match.group(1)
                    
                    # Parse cell data
                    if len(cells) >= 3:
                        # Find org/title cell (has multiple lines with Pakistan)
                        for cell in cells:
                            text = cell.inner_text().strip()
                            if 'Pakistan' in text or len(text) > 80:
                                lines = [l.strip() for l in text.split('\n') if l.strip()]
                                if lines:
                                    tender['organization'] = lines[0]
                                if len(lines) >= 2:
                                    tender['title'] = lines[1]
                                if len(lines) >= 3:
                                    extra = lines[2]
                                    if extra != tender.get('title'):
                                        if '/' in extra or re.match(r'^[A-Z0-9-]+$', extra):
                                            tender['tender_no'] = extra
                                        elif len(extra) > 5:
                                            tender['title'] = tender.get('title', '') + ' ' + extra
                                if len(lines) >= 4:
                                    tender['tender_no'] = tender.get('tender_no') or lines[-1]
                                break
                        
                        # Find date
                        for cell in cells:
                            text = cell.inner_text().strip()
                            if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d', text):
                                tender['closing_date'] = text.split('\n')[0].strip()
                                break
                        
                        # Find status (usually last cell)
                        if len(cells) >= 4:
                            last_text = cells[-1].inner_text().strip()
                            if len(last_text) < 30 and 'Jan' not in last_text and 'Feb' not in last_text:
                                tender['status'] = last_text
                    
                    if tender.get('organization') or tender.get('title') or tender.get('ts_no'):
                        tenders.append(tender)
                        
                except:
                    continue
                    
        except Exception as e:
            print(f"Extract error: {e}")
            
        return tenders

    def get_detail_by_clicking(self, page: Page, tender: Dict) -> Dict:
        """Click on tender row to get detail page and extract info"""
        detail = {}
        
        try:
            # Find and click the TS link
            ts_no = tender.get('ts_no', '')
            if ts_no:
                link = page.query_selector(f'a:has-text("{ts_no}")')
                if link:
                    link.click()
                    time.sleep(2)
                    
                    # Extract from detail page
                    body = page.inner_text('body')
                    lines = [l.strip() for l in body.split('\n') if l.strip()]
                    
                    desc_parts = []
                    in_details = False
                    
                    for line in lines:
                        ll = line.lower()
                        
                        # Skip headers
                        if any(s in ll for s in ['login', 'ppra', 'حکومت', 'only 10 days']):
                            continue
                        
                        if 'tender details' in ll:
                            in_details = True
                            continue
                        if 'downloads' in ll:
                            in_details = False
                            continue
                        
                        # Parse key:value
                        if ':' in line and len(line) < 500:
                            key, val = line.split(':', 1)
                            key = key.strip().lower()
                            val = val.strip()
                            
                            if val:
                                if 'organization' in key or 'agency' in key:
                                    detail['organization'] = val
                                elif 'title' in key:
                                    detail['title'] = val
                                elif 'tender no' in key:
                                    detail['tender_no'] = val
                                elif 'closing' in key:
                                    detail['closing_date'] = val
                                elif 'opening' in key:
                                    detail['opening_date'] = val
                                elif 'publish' in key:
                                    detail['published_date'] = val
                                elif 'cost' in key or 'estimated' in key:
                                    detail['estimated_cost'] = val
                                elif 'type' in key or 'category' in key:
                                    detail['procurement_type'] = val
                                elif 'method' in key:
                                    detail['procurement_method'] = val
                                elif 'location' in key:
                                    detail['location'] = val
                                elif 'ntn' in key:
                                    detail['ntn'] = val
                                elif 'description' in key or 'scope' in key:
                                    desc_parts.append(val)
                        
                        # Collect content
                        elif in_details and len(line) > 30:
                            if not any(s in ll for s in ['view', 'download', 'click']):
                                desc_parts.append(line)
                    
                    if desc_parts:
                        detail['description'] = ' | '.join(desc_parts[:6])[:2000]
                    
                    # Go back
                    page.go_back()
                    time.sleep(1)
                    
        except Exception as e:
            pass
            
        return detail

    def normalize_api_record(self, record: Dict) -> Dict:
        """Convert API record to standard format"""
        tender = {}
        
        mappings = {
            'tender_id': ['procurementPlansDetailID', 'id'],
            'ts_no': ['tsNo', 'tSNo'],
            'tender_no': ['tenderNo', 'referenceNo'],
            'title': ['procurementActivityName', 'title'],
            'organization': ['departmentName', 'organization'],
            'procurement_type': ['procurementType'],
            'category': ['procurementCategory'],
            'sector': ['sectorName'],
            'status': ['activityStatus'],
            'published_date': ['publishingDate'],
            'closing_date': ['closingDateAndTime'],
            'opening_date': ['openingDateAndTime'],
            'estimated_cost': ['estimatedCostInPKR'],
            'ntn': ['ntn'],
        }
        
        for std, options in mappings.items():
            for opt in options:
                if opt in record and record[opt]:
                    tender[std] = str(record[opt]).strip()
                    break
        
        return tender

    def scrape(self, max_pages: int = 60, fetch_details: bool = True, max_details: int = 100) -> List[Dict]:
        """Main scraper"""
        print("=" * 60)
        print("PPRA Pakistan Tenders Scraper")
        print("=" * 60)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.on('response', self.handle_response)
            
            print(f"\nLoading: {TENDERS_URL}")
            page.goto(TENDERS_URL, wait_until='networkidle', timeout=60000)
            time.sleep(5)
            
            all_tenders = []
            seen_keys = set()
            page_num = 1
            stale_count = 0
            
            while page_num <= max_pages:
                print(f"Page {page_num}...", end=' ')
                
                tenders = self.extract_tenders_with_links(page)
                
                new_tenders = []
                for t in tenders:
                    key = t.get('ts_no') or (t.get('title', '') + t.get('organization', ''))[:50]
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        new_tenders.append(t)
                
                if new_tenders:
                    all_tenders.extend(new_tenders)
                    print(f"{len(new_tenders)} new ({len(all_tenders)} total)")
                    stale_count = 0
                else:
                    print("no new")
                    stale_count += 1
                    if stale_count >= 3:
                        break
                
                # Next page
                try:
                    clicked = False
                    for sel in ['button:has-text("Next")', 'a:has-text("Next")', '.next']:
                        try:
                            btn = page.query_selector(sel)
                            if btn and btn.is_visible():
                                btn.click()
                                time.sleep(2)
                                clicked = True
                                break
                        except:
                            continue
                    
                    if not clicked:
                        for pl in page.query_selector_all('.pagination a, nav a'):
                            try:
                                txt = pl.inner_text().strip()
                                if txt == str(page_num + 1) or txt in ['>', '»']:
                                    pl.click()
                                    time.sleep(2)
                                    clicked = True
                                    break
                            except:
                                continue
                    
                    if clicked:
                        page_num += 1
                    else:
                        break
                except:
                    break
            
            # Add API data
            if self.api_data:
                print(f"\nAPI data: {len(self.api_data)} records")
                for record in self.api_data:
                    t = self.normalize_api_record(record)
                    if t.get('title') or t.get('organization'):
                        key = t.get('ts_no') or t.get('tender_id') or t.get('title', '')[:30]
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_tenders.append(t)
            
            print(f"\nTotal unique: {len(all_tenders)}")
            self.tenders = all_tenders
            
            # Fetch details by clicking
            if fetch_details:
                with_ts = [t for t in self.tenders if t.get('ts_no')]
                print(f"Tenders with TS#: {len(with_ts)}")
                
                if with_ts:
                    print(f"Fetching details for {min(len(with_ts), max_details)} tenders...")
                    
                    # Go back to first page
                    page.goto(TENDERS_URL, wait_until='networkidle', timeout=60000)
                    time.sleep(3)
                    
                    count = 0
                    for t in with_ts[:max_details]:
                        count += 1
                        ts = t['ts_no']
                        print(f"  {count}/{min(len(with_ts), max_details)}: {ts}    ", end='\r')
                        
                        detail = self.get_detail_by_clicking(page, t)
                        for k, v in detail.items():
                            if v and (not t.get(k) or len(str(v)) > len(str(t.get(k, '')))):
                                t[k] = v
                        
                        time.sleep(0.5)
                    
                    print(f"\nFetched {count} details")
            
            browser.close()
        
        return self.tenders

    def save_to_csv(self, filename: str = OUTPUT_FILE) -> str:
        """Save results"""
        if not self.tenders:
            return ""
        
        keys = set()
        for t in self.tenders:
            keys.update(t.keys())
        
        # Remove internal keys
        keys.discard('detail_path')
        
        order = [
            'tender_id', 'ts_no', 'tender_no', 'title', 'organization',
            'procurement_type', 'category', 'sector', 'status',
            'published_date', 'closing_date', 'opening_date',
            'estimated_cost', 'location', 'procurement_method',
            'ntn', 'contact', 'description'
        ]
        
        cols = [c for c in order if c in keys]
        cols.extend(sorted(k for k in keys if k not in cols))
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.tenders)
        
        print(f"\nSaved: {len(self.tenders)} tenders to {filename}")
        print(f"Columns: {', '.join(cols)}")
        return filename


def main():
    scraper = PPRAScraper()
    tenders = scraper.scrape(max_pages=60, fetch_details=True, max_details=100)
    
    if tenders:
        scraper.save_to_csv()
        print(f"\n{'=' * 60}")
        print(f"DONE: {len(tenders)} tenders scraped")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
