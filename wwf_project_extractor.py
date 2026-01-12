#!/usr/bin/env python3
"""
WWF Pakistan Consultancy Projects Complete Extractor
=====================================================
This script performs the following tasks:
1. Scrapes project information from https://wwf.org.pk/consultancy/
2. Downloads each PDF document
3. Extracts text content from PDFs
4. Saves all data to a CSV file
5. Deletes temporary PDF files after extraction

Author: Auto-generated
Date: 2026-01-12
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber
import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse
import tempfile


class WWFProjectExtractor:
    """Complete extractor for WWF Pakistan consultancy projects."""
    
    def __init__(self, output_file='wwf_consultancy_projects.csv'):
        self.url = "https://wwf.org.pk/consultancy/"
        self.base_url = "https://wwf.org.pk"
        self.output_file = output_file
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.projects = []
    
    def clean_text(self, text):
        """Clean and normalize text."""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text).strip()
        text = ''.join(char for char in text if char.isprintable() or char in ['\n', '\t'])
        return text
    
    def fetch_page(self):
        """Fetch the webpage content."""
        print(f"[1/4] Fetching webpage: {self.url}")
        try:
            response = requests.get(self.url, headers=self.headers, timeout=30)
            response.raise_for_status()
            print("      Webpage fetched successfully!")
            return response.text
        except requests.RequestException as e:
            print(f"      Error fetching page: {e}")
            return None
    
    def extract_projects_from_html(self, html_content):
        """Extract project information from HTML content."""
        print("[2/4] Extracting project information from webpage...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        projects = []
        
        # Try to extract from tables first
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header
                cells = row.find_all(['td', 'th'])
                if cells:
                    project = {}
                    header_row = rows[0] if rows else None
                    header_cells = header_row.find_all(['td', 'th']) if header_row else []
                    
                    for i, cell in enumerate(cells):
                        header_name = self.clean_text(header_cells[i].get_text()) if i < len(header_cells) else f"Column_{i+1}"
                        project[header_name] = self.clean_text(cell.get_text())
                        
                        link = cell.find('a')
                        if link and link.get('href'):
                            project[f"{header_name}_Link"] = link.get('href')
                    
                    if project:
                        projects.append(project)
        
        # If no table data, try extracting all links with context
        if not projects:
            projects = self._extract_links_with_context(soup)
        
        # Filter out navigation items
        filtered = []
        skip_terms = ['home', 'about', 'contact', 'facebook', 'twitter', 'instagram', 
                      'linkedin', 'menu', 'search', 'login', 'subscribe', 'copyright']
        
        for p in projects:
            title = p.get('Title', '').lower()
            if not any(term == title for term in skip_terms):
                filtered.append(p)
        
        self.projects = filtered if filtered else projects
        print(f"      Found {len(self.projects)} projects!")
        return self.projects
    
    def _extract_links_with_context(self, soup):
        """Extract all links with their context."""
        projects = []
        all_links = soup.find_all('a')
        
        for link in all_links:
            href = link.get('href', '')
            text = self.clean_text(link.get_text())
            
            if not text or len(text) < 5:
                continue
            if href in ['#', '', '/'] or 'javascript:' in href:
                continue
            
            # Make absolute URL
            if href and not href.startswith('http'):
                if href.startswith('/'):
                    href = self.base_url.rstrip('/') + href
                else:
                    href = self.base_url.rstrip('/') + '/' + href
            
            # Get context from parent
            parent = link.find_parent(['li', 'div', 'td', 'article', 'section'])
            description = ""
            date = ""
            
            if parent:
                parent_text = self.clean_text(parent.get_text())
                if parent_text != text:
                    description = parent_text
                
                # Look for date patterns
                date_match = re.search(
                    r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|'
                    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',
                    parent_text, re.I
                )
                if date_match:
                    date = date_match.group()
            
            project = {
                'Title': text,
                'Link': href,
                'Description': description if description != text else "",
                'Date': date
            }
            
            # Check for PDF links
            if 'pdf' in href.lower():
                project['PDF_Link'] = href
                project['PDF_Title'] = text
            
            # Avoid duplicates
            if not any(p.get('Title') == text and p.get('Link') == href for p in projects):
                projects.append(project)
        
        return projects
    
    def download_pdf(self, url, temp_path):
        """Download a PDF file."""
        try:
            response = requests.get(url, headers=self.headers, timeout=30, stream=True)
            response.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except requests.RequestException:
            return False
    
    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF file."""
        try:
            text_content = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
            
            full_text = '\n'.join(text_content)
            return self.clean_text(full_text)
        except Exception:
            return ""
    
    def process_pdfs(self):
        """Download and extract text from all PDFs."""
        print("[3/4] Downloading PDFs and extracting text...")
        
        # Count PDFs
        pdf_count = sum(1 for p in self.projects if p.get('PDF_Link'))
        print(f"      Found {pdf_count} PDF links to process")
        
        processed = 0
        success = 0
        
        for project in self.projects:
            pdf_url = project.get('PDF_Link', '')
            
            if not pdf_url or not str(pdf_url).strip():
                project['PDF_Text_Content'] = ""
                continue
            
            pdf_url = str(pdf_url).strip()
            processed += 1
            
            # Display progress
            filename = os.path.basename(urlparse(pdf_url).path)[:40]
            print(f"      [{processed}/{pdf_count}] {filename}...", end=" ")
            
            # Create temp file
            temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_path = temp_pdf.name
            temp_pdf.close()
            
            try:
                if self.download_pdf(pdf_url, temp_path):
                    text_content = self.extract_text_from_pdf(temp_path)
                    
                    if text_content:
                        # Limit to 10000 chars
                        if len(text_content) > 10000:
                            text_content = text_content[:10000] + "... [truncated]"
                        
                        project['PDF_Text_Content'] = text_content
                        success += 1
                        print(f"OK ({len(text_content)} chars)")
                    else:
                        project['PDF_Text_Content'] = ""
                        print("No text")
                else:
                    project['PDF_Text_Content'] = ""
                    print("Download failed")
            
            finally:
                # Delete temp PDF
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            # Small delay
            time.sleep(0.3)
        
        print(f"      Completed: {success}/{processed} PDFs extracted successfully")
    
    def save_to_csv(self):
        """Save all data to CSV file."""
        print(f"[4/4] Saving data to {self.output_file}...")
        
        if not self.projects:
            print("      No projects to save!")
            return False
        
        # Define column order
        preferred_order = ['Title', 'Description', 'PDF_Text_Content', 'Date', 
                          'Link', 'PDF_Link', 'PDF_Title']
        
        # Get all unique keys
        all_keys = set()
        for project in self.projects:
            all_keys.update(project.keys())
        
        columns = [col for col in preferred_order if col in all_keys]
        columns.extend([col for col in sorted(all_keys) if col not in columns])
        
        # Create DataFrame
        df = pd.DataFrame(self.projects)
        df = df.reindex(columns=columns)
        
        # Save to CSV
        df.to_csv(self.output_file, index=False, encoding='utf-8-sig')
        
        print(f"      Saved {len(self.projects)} projects to {self.output_file}")
        return True
    
    def run(self):
        """Run the complete extraction process."""
        print("=" * 60)
        print("WWF PAKISTAN CONSULTANCY PROJECTS EXTRACTOR")
        print("=" * 60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        
        # Step 1: Fetch webpage
        html_content = self.fetch_page()
        if not html_content:
            print("Failed to fetch webpage. Exiting.")
            return False
        
        # Step 2: Extract project info
        self.extract_projects_from_html(html_content)
        if not self.projects:
            print("No projects found. Exiting.")
            return False
        
        # Step 3: Process PDFs
        self.process_pdfs()
        
        # Step 4: Save to CSV
        self.save_to_csv()
        
        # Summary
        print("-" * 60)
        print("EXTRACTION COMPLETE!")
        print("-" * 60)
        print(f"Total projects: {len(self.projects)}")
        pdf_extracted = sum(1 for p in self.projects if p.get('PDF_Text_Content'))
        print(f"PDFs with text: {pdf_extracted}")
        print(f"Output file: {self.output_file}")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        return True


def main():
    """Main entry point."""
    extractor = WWFProjectExtractor(output_file='wwf_consultancy_projects.csv')
    extractor.run()


if __name__ == "__main__":
    main()
