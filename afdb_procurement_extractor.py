#!/usr/bin/env python3
"""
African Development Bank Corporate Procurement Extractor
Extracts procurement notices from https://www.afdb.org/en/about-us/corporate-procurement
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber
import requests
import os
import re
import time
from datetime import datetime
from urllib.parse import urljoin
import tempfile


class AFDBProcurementExtractor:
    def __init__(self, output_file='afdb_procurement_notices.csv'):
        self.base_url = "https://www.afdb.org"
        self.start_url = "https://www.afdb.org/en/about-us/corporate-procurement"
        self.output_file = output_file
        self.notices = []
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    def clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text).strip()
        return ''.join(c for c in text if c.isprintable() or c in ['\n', '\t'])
    
    def wait_for_cloudflare(self, page, max_wait=30):
        """Wait for Cloudflare challenge to complete."""
        for _ in range(max_wait):
            title = page.title()
            if "Just a moment" not in title and "Cloudflare" not in title:
                return True
            time.sleep(1)
        return False
    
    def get_total_pages(self, page):
        try:
            last_link = page.query_selector('a[title="Go to last page"]')
            if last_link:
                href = last_link.get_attribute('href')
                match = re.search(r'page=(\d+)', href)
                if match:
                    return int(match.group(1)) + 1
            return 1
        except:
            return 1
    
    def extract_notices_from_page(self, page, page_num):
        notices = []
        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        links = soup.find_all('a', href=re.compile(r'/corporate-procurement/[^?]'))
        seen_urls = set()
        
        skip_terms = ['contract awards', 'vendor kiosk', 'contacts', 'procurement notices', 
                      'corporate procurement services', 'project-related']
        
        for link in links:
            href = link.get('href', '')
            title = self.clean_text(link.get_text())
            
            if not title or len(title) < 10:
                continue
            if any(skip in title.lower() for skip in skip_terms):
                continue
            
            full_url = urljoin(self.base_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            notice = {
                'Title': title,
                'URL': full_url,
                'Page_Found': page_num + 1
            }
            notices.append(notice)
        
        return notices
    
    def get_notice_details(self, page, notice):
        try:
            page.goto(notice['URL'], timeout=90000)
            self.wait_for_cloudflare(page)
            time.sleep(2)
            
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            main = soup.find(['article', 'main', 'div'], class_=re.compile(r'content', re.I))
            if main:
                paragraphs = main.find_all('p')
                full_text = ' '.join([self.clean_text(p.get_text()) for p in paragraphs])
                if full_text:
                    notice['Full_Description'] = full_text[:5000]
                
                pdf_links = main.find_all('a', href=re.compile(r'\.pdf', re.I))
                if pdf_links:
                    notice['PDF_Links'] = '; '.join([urljoin(self.base_url, l.get('href')) for l in pdf_links[:5]])
            
            return True
        except Exception as e:
            print(f"Error: {str(e)[:50]}")
            return False
    
    def download_pdf_text(self, pdf_url):
        try:
            response = requests.get(pdf_url, headers=self.headers, timeout=30, stream=True)
            response.raise_for_status()
            
            temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_path = temp_pdf.name
            temp_pdf.close()
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            text_content = []
            with pdfplumber.open(temp_path) as pdf:
                for pg in pdf.pages[:10]:
                    pg_text = pg.extract_text()
                    if pg_text:
                        text_content.append(pg_text)
            
            os.remove(temp_path)
            return self.clean_text('\n'.join(text_content))[:10000]
        except:
            return ""
    
    def save_to_csv(self):
        if not self.notices:
            return
        
        columns = ['Title', 'Full_Description', 'URL', 'PDF_Links', 'PDF_Text_Content', 'Page_Found']
        df = pd.DataFrame(self.notices)
        existing = [c for c in columns if c in df.columns]
        df = df[existing + [c for c in df.columns if c not in existing]]
        df.to_csv(self.output_file, index=False, encoding='utf-8-sig')
        print(f"Saved {len(self.notices)} notices to {self.output_file}")
    
    def run(self):
        print("=" * 60)
        print("AFDB CORPORATE PROCUREMENT EXTRACTOR")
        print("=" * 60)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(flush=True)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            print("\n[1/4] Fetching listing pages...", flush=True)
            page.goto(self.start_url, timeout=120000)
            
            # Wait for Cloudflare
            print("Waiting for page to load...", flush=True)
            self.wait_for_cloudflare(page, max_wait=60)
            time.sleep(5)
            
            total_pages = self.get_total_pages(page)
            print(f"Found {total_pages} pages", flush=True)
            
            print("\n[2/4] Extracting notices...", flush=True)
            all_notices = []
            
            for pg_num in range(min(total_pages, 41)):
                if pg_num > 0:
                    page.goto(f"{self.start_url}?page={pg_num}", timeout=90000)
                    self.wait_for_cloudflare(page)
                    time.sleep(3)
                
                notices = self.extract_notices_from_page(page, pg_num)
                all_notices.extend(notices)
                print(f"  Page {pg_num + 1}: {len(notices)} notices (Total: {len(all_notices)})", flush=True)
            
            # Remove duplicates
            seen = set()
            for n in all_notices:
                if n['URL'] not in seen:
                    seen.add(n['URL'])
                    self.notices.append(n)
            
            print(f"\nTotal unique notices: {len(self.notices)}", flush=True)
            
            print("\n[3/4] Fetching details and PDFs...", flush=True)
            for i, notice in enumerate(self.notices, 1):
                print(f"  [{i}/{len(self.notices)}] {notice['Title'][:45]}...", end=" ", flush=True)
                
                self.get_notice_details(page, notice)
                
                if notice.get('PDF_Links'):
                    first_pdf = notice['PDF_Links'].split(';')[0].strip()
                    pdf_text = self.download_pdf_text(first_pdf)
                    if pdf_text:
                        notice['PDF_Text_Content'] = pdf_text
                        print(f"OK ({len(pdf_text)} chars)", flush=True)
                    else:
                        print("No PDF text", flush=True)
                else:
                    print("No PDF", flush=True)
                
                time.sleep(0.5)
            
            browser.close()
        
        print("\n[4/4] Saving CSV...", flush=True)
        self.save_to_csv()
        
        print("\n" + "=" * 60)
        print("COMPLETE!")
        print(f"Notices: {len(self.notices)}")
        print(f"Output: {self.output_file}")
        print("=" * 60, flush=True)


def main():
    extractor = AFDBProcurementExtractor()
    extractor.run()


if __name__ == "__main__":
    main()
