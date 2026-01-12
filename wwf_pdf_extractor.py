#!/usr/bin/env python3
"""
WWF Pakistan Consultancy PDF Text Extractor
Downloads PDFs from the scraped data, extracts text content,
and updates the CSV file with the extracted descriptions.
"""

import requests
import pandas as pd
import pdfplumber
import os
import re
import time
from urllib.parse import urlparse
import tempfile


def clean_text(text):
    """Clean and normalize extracted text."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    text = ''.join(char for char in text if char.isprintable() or char in ['\n', '\t'])
    return text


def download_pdf(url, temp_path):
    """Download a PDF file from URL to temporary path."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.RequestException as e:
        print(f"  Error downloading: {e}")
        return False


def extract_text_from_pdf(pdf_path):
    """Extract text content from a PDF file using pdfplumber."""
    try:
        text_content = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)
        
        full_text = '\n'.join(text_content)
        return clean_text(full_text)
    except Exception as e:
        print(f"  Error extracting text: {e}")
        return ""


def process_pdfs(input_csv, output_csv):
    """Process all PDFs in the CSV and extract their text content."""
    print(f"Reading CSV: {input_csv}")
    df = pd.read_csv(input_csv)
    
    if 'PDF_Text_Content' not in df.columns:
        df['PDF_Text_Content'] = ""
    
    pdf_links = df['PDF_Link'].dropna()
    total_pdfs = len(pdf_links)
    print(f"Found {total_pdfs} PDF links to process\n")
    
    processed = 0
    success = 0
    failed = 0
    
    for idx, row in df.iterrows():
        pdf_url = row.get('PDF_Link', '')
        
        if pd.isna(pdf_url) or not pdf_url or not str(pdf_url).strip():
            continue
        
        pdf_url = str(pdf_url).strip()
        processed += 1
        
        filename = os.path.basename(urlparse(pdf_url).path)[:50]
        print(f"[{processed}/{total_pdfs}] Processing: {filename}...")
        
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_path = temp_pdf.name
        temp_pdf.close()
        
        try:
            if download_pdf(pdf_url, temp_path):
                text_content = extract_text_from_pdf(temp_path)
                
                if text_content:
                    if len(text_content) > 10000:
                        text_content = text_content[:10000] + "... [truncated]"
                    
                    df.at[idx, 'PDF_Text_Content'] = text_content
                    success += 1
                    print(f"  Extracted {len(text_content)} characters")
                else:
                    failed += 1
                    print(f"  No text extracted")
            else:
                failed += 1
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        time.sleep(0.5)
    
    cols = list(df.columns)
    if 'PDF_Text_Content' in cols:
        cols.remove('PDF_Text_Content')
        if 'Description' in cols:
            desc_idx = cols.index('Description') + 1
            cols.insert(desc_idx, 'PDF_Text_Content')
        else:
            cols.append('PDF_Text_Content')
    df = df[cols]
    
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    
    print("\n" + "=" * 50)
    print("PROCESSING COMPLETE")
    print("=" * 50)
    print(f"Total PDFs processed: {processed}")
    print(f"Successfully extracted: {success}")
    print(f"Failed/Empty: {failed}")
    print(f"Output saved to: {output_csv}")
    
    return df


def main():
    """Main function."""
    input_csv = 'wwf_consultancy_projects.csv'
    output_csv = 'wwf_consultancy_projects.csv'
    
    if not os.path.exists(input_csv):
        print(f"Error: {input_csv} not found. Please run wwf_scraper.py first.")
        return
    
    process_pdfs(input_csv, output_csv)


if __name__ == "__main__":
    main()
