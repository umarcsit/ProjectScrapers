#!/usr/bin/env python3
"""
UNGM (UN Global Marketplace) Tender Scraper
Scrapes tender information from https://www.ungm.org/Public/Notice
Including detailed descriptions from each tender's detail page.

Author: Auto-generated
Date: 2025
"""

import csv
import time
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================================
# CONFIGURATION
# ============================================================================
BASE_URL = "https://www.ungm.org"
NOTICE_URL = f"{BASE_URL}/Public/Notice"

# Maximum records to scrape (set to None for all available)
MAX_RECORDS = 50

# Output file name
OUTPUT_FILE = "ungm_tenders.csv"

# Seconds to wait between requests (to be respectful to the server)
REQUEST_DELAY = 2

# ============================================================================

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ungm_scraper.log"),
    ],
)
logger = logging.getLogger(__name__)


def setup_driver() -> webdriver.Chrome:
    """Set up Chrome WebDriver with headless options."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)
    return driver


def get_total_records(driver: webdriver.Chrome) -> int:
    """Get total number of records available."""
    try:
        wait = WebDriverWait(driver, 20)
        total_label = wait.until(
            EC.presence_of_element_located((By.ID, "noticeSearchTotal"))
        )
        total_text = total_label.text.strip()
        total = int(total_text.replace(",", ""))
        return total
    except Exception as e:
        logger.error(f"Error getting total records: {e}")
        return 0


def wait_for_table_load(driver: webdriver.Chrome, timeout: int = 30) -> bool:
    """Wait for the tender table to load."""
    try:
        wait = WebDriverWait(driver, timeout)
        # Wait for data rows to be present
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".dataRow.notice-table")
            )
        )
        time.sleep(2)
        return True
    except TimeoutException:
        logger.warning("Timeout waiting for table to load")
        return False


def scroll_to_load_all_records(driver: webdriver.Chrome, target_count: int) -> int:
    """Scroll down to load records via infinite scroll."""
    logger.info(f"Loading records via infinite scroll (target: {target_count})...")
    
    last_count = 0
    no_change_count = 0
    max_no_change = 5
    
    while True:
        # Get current count
        rows = driver.find_elements(By.CSS_SELECTOR, ".dataRow.notice-table")
        current_count = len(rows)
        
        logger.info(f"  Loaded {current_count} records...")
        
        # Check if we have enough
        if current_count >= target_count:
            logger.info(f"  Reached target of {target_count} records")
            break
        
        # Check if loading stopped
        if current_count == last_count:
            no_change_count += 1
            if no_change_count >= max_no_change:
                logger.info(f"  No more records loading. Stopped at {current_count}")
                break
        else:
            no_change_count = 0
        
        last_count = current_count
        
        # Scroll down
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Wait for content to load
        
        # Try scrolling in smaller increments if needed
        if no_change_count > 2:
            driver.execute_script(
                "window.scrollBy(0, window.innerHeight * 2);"
            )
            time.sleep(1)
    
    final_count = len(driver.find_elements(By.CSS_SELECTOR, ".dataRow.notice-table"))
    return final_count


def extract_all_tenders_basic_info(driver: webdriver.Chrome) -> List[Dict]:
    """Extract basic tender information from all visible rows."""
    tenders = []
    seen_ids = set()

    try:
        rows = driver.find_elements(By.CSS_SELECTOR, ".dataRow.notice-table")
        logger.info(f"Extracting basic info from {len(rows)} rows...")

        for row in rows:
            try:
                tender = {}

                # Get notice ID
                notice_id = row.get_attribute("data-noticeid")
                if not notice_id or notice_id in seen_ids:
                    continue
                    
                seen_ids.add(notice_id)
                tender["Notice_ID"] = notice_id
                tender["Detail_URL"] = f"{BASE_URL}/Public/Notice/{notice_id}"

                # Title
                try:
                    title_span = row.find_element(By.CSS_SELECTOR, ".ungm-title")
                    tender["Title"] = title_span.text.strip()
                except NoSuchElementException:
                    tender["Title"] = ""

                # Deadline
                try:
                    deadline_cell = row.find_element(By.CSS_SELECTOR, ".deadline")
                    deadline_spans = deadline_cell.find_elements(By.TAG_NAME, "span")
                    if deadline_spans:
                        deadline_text = deadline_spans[0].text.strip()
                        deadline_text = re.sub(r'\s+', ' ', deadline_text)
                        tender["Deadline"] = deadline_text
                    else:
                        tender["Deadline"] = ""
                except NoSuchElementException:
                    tender["Deadline"] = ""

                # UN Organization
                try:
                    agency_cell = row.find_element(By.CSS_SELECTOR, ".resultAgency")
                    tender["UN_Organization"] = agency_cell.text.strip()
                except NoSuchElementException:
                    tender["UN_Organization"] = ""

                # Reference
                try:
                    ref_cell = row.find_element(
                        By.CSS_SELECTOR, "[data-description='Reference']"
                    )
                    tender["Reference"] = ref_cell.text.strip()
                except NoSuchElementException:
                    tender["Reference"] = ""

                # Get all cells for remaining info
                cells = row.find_elements(By.CSS_SELECTOR, "[role='cell']")
                cell_texts = []
                for cell in cells:
                    cell_class = cell.get_attribute("class") or ""
                    if any(c in cell_class for c in [
                        "resultOptions", "resultTitle", "deadline", 
                        "resultAgency", "resultInfo1"
                    ]):
                        continue
                    text = cell.text.strip()
                    if text:
                        cell_texts.append(text)

                # Assign remaining values (Published Date, Type, Country)
                tender["Published_Date"] = cell_texts[0] if len(cell_texts) >= 1 else ""
                tender["Type"] = cell_texts[1] if len(cell_texts) >= 2 else ""
                tender["Country"] = cell_texts[2] if len(cell_texts) >= 3 else ""

                # Sustainability badge
                try:
                    row.find_element(By.CSS_SELECTOR, ".sustainability")
                    tender["Sustainability"] = "Yes"
                except NoSuchElementException:
                    tender["Sustainability"] = "No"

                tenders.append(tender)

            except Exception as e:
                logger.warning(f"Error extracting row: {e}")
                continue

    except Exception as e:
        logger.error(f"Error extracting tenders: {e}")

    return tenders


def get_tender_details(driver: webdriver.Chrome, detail_url: str) -> Dict:
    """Get detailed information from a tender's detail page."""
    details = {
        "Description": "",
        "Contact_Name": "",
        "Contact_Email": "",
        "Contact_Address": "",
        "Documents": "",
        "Beneficiary_Country": "",
        "UNSPSC_Codes": "",
    }

    try:
        driver.get(detail_url)
        time.sleep(REQUEST_DELAY)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "noticeDetail")))
        time.sleep(1)

        # Extract description
        try:
            # Find the Description title and get following content
            title_divs = driver.find_elements(By.CSS_SELECTOR, "div.title")
            for title_div in title_divs:
                if "Description" in title_div.text:
                    parent = title_div.find_element(By.XPATH, "./..")
                    full_text = parent.text
                    description = full_text.replace("Description", "", 1).strip()
                    if description:
                        # Clean up HTML artifacts
                        description = re.sub(r'\s+', ' ', description)
                        details["Description"] = description[:10000]
                        break

            # Alternative: look for tab content
            if not details["Description"]:
                try:
                    overview_tab = driver.find_element(By.ID, "overview-tab")
                    text = overview_tab.text.strip()
                    if len(text) > 50:
                        details["Description"] = text[:10000]
                except NoSuchElementException:
                    pass

        except Exception as e:
            logger.debug(f"Could not extract description: {e}")

        # Extract contact information
        try:
            contact_section = driver.find_element(By.ID, "contactDetails")
            contact_text = contact_section.text
            details["Contact_Name"] = contact_text[:500] if contact_text else ""

            # Try to find email
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', contact_text)
            if email_match:
                details["Contact_Email"] = email_match.group()

        except NoSuchElementException:
            try:
                contact_div = driver.find_element(By.CSS_SELECTOR, ".contactDetails")
                details["Contact_Name"] = contact_div.text[:500]
            except NoSuchElementException:
                pass

        # Extract documents
        try:
            doc_links = driver.find_elements(
                By.CSS_SELECTOR, "a[href*='Document'], a[href*='download']"
            )
            docs = [link.text.strip() for link in doc_links if link.text.strip()]
            details["Documents"] = "; ".join(docs[:10])  # Limit to 10 docs
        except Exception:
            pass

        # Extract UNSPSC codes
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            codes = re.findall(r'\b\d{8}\b', page_text)
            if codes:
                details["UNSPSC_Codes"] = "; ".join(set(codes[:5]))
        except Exception:
            pass

        # Extract beneficiary country
        try:
            elements = driver.find_elements(
                By.XPATH, "//*[contains(text(), 'Beneficiary')]"
            )
            for elem in elements:
                parent = elem.find_element(By.XPATH, "./..")
                text = parent.text
                if "Beneficiary" in text:
                    country_text = re.sub(r'.*Beneficiary\s*(Country|country)?:?\s*', '', text)
                    details["Beneficiary_Country"] = country_text[:200]
                    break
        except Exception:
            pass

    except TimeoutException:
        logger.warning(f"Timeout loading detail page: {detail_url}")
    except Exception as e:
        logger.error(f"Error getting tender details from {detail_url}: {e}")

    return details


def save_to_csv(tenders: List[Dict], filename: str):
    """Save tender data to CSV file."""
    if not tenders:
        logger.warning("No tenders to save")
        return

    # Define column order for comprehensive output
    columns = [
        "Notice_ID",
        "Title",
        "Reference",
        "UN_Organization",
        "Published_Date",
        "Deadline",
        "Type",
        "Country",
        "Sustainability",
        "Beneficiary_Country",
        "Contact_Name",
        "Contact_Email",
        "Contact_Address",
        "UNSPSC_Codes",
        "Documents",
        "Description",
        "Detail_URL",
    ]

    # Ensure all columns exist in each tender
    for tender in tenders:
        for col in columns:
            if col not in tender:
                tender[col] = ""

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(tenders)

    logger.info(f"Saved {len(tenders)} tenders to {filename}")


def main():
    """Main scraper function."""
    logger.info("=" * 60)
    logger.info("UNGM Tender Scraper Started")
    logger.info(f"Target URL: {NOTICE_URL}")
    logger.info(f"Max Records: {MAX_RECORDS if MAX_RECORDS else 'All'}")
    logger.info("=" * 60)

    driver = None
    all_tenders = []
    total_available = 0

    try:
        # Setup WebDriver
        logger.info("Setting up Chrome WebDriver...")
        driver = setup_driver()

        # Navigate to notice page
        logger.info(f"Navigating to {NOTICE_URL}...")
        driver.get(NOTICE_URL)

        # Wait for initial load
        if not wait_for_table_load(driver, timeout=30):
            logger.error("Failed to load initial page")
            return

        # Get total available records
        total_available = get_total_records(driver)
        logger.info(f"\n{'='*60}")
        logger.info(f"TOTAL RECORDS AVAILABLE ON UNGM: {total_available}")
        logger.info(f"{'='*60}\n")

        # Determine how many records to scrape
        records_to_scrape = (
            min(MAX_RECORDS, total_available) if MAX_RECORDS else total_available
        )
        logger.info(f"Will scrape up to {records_to_scrape} records")

        # Step 1: Scroll to load all needed records
        loaded_count = scroll_to_load_all_records(driver, records_to_scrape)
        logger.info(f"\nLoaded {loaded_count} records via infinite scroll")

        # Step 2: Extract basic info from all loaded records
        tenders_basic = extract_all_tenders_basic_info(driver)
        logger.info(f"Extracted basic info for {len(tenders_basic)} unique tenders")

        # Limit to MAX_RECORDS
        tenders_basic = tenders_basic[:records_to_scrape]

        # Step 3: Get detailed info for each tender
        logger.info(f"\nFetching detailed information for {len(tenders_basic)} tenders...")
        
        for i, tender in enumerate(tenders_basic):
            logger.info(
                f"  [{i + 1}/{len(tenders_basic)}] "
                f"Getting details for: {tender.get('Title', 'Unknown')[:50]}..."
            )

            if tender.get("Detail_URL"):
                details = get_tender_details(driver, tender["Detail_URL"])
                tender.update(details)

            all_tenders.append(tender)

            # Save progress periodically
            if (i + 1) % 10 == 0:
                save_to_csv(all_tenders, OUTPUT_FILE)
                logger.info(f"Progress saved: {len(all_tenders)} records")

        # Final save
        save_to_csv(all_tenders, OUTPUT_FILE)

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("SCRAPING COMPLETED")
        logger.info(f"Total records available on UNGM: {total_available}")
        logger.info(f"Total records scraped: {len(all_tenders)}")
        logger.info(f"Output file: {OUTPUT_FILE}")
        logger.info("=" * 60)

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Total records available on UNGM: {total_available}")
        print(f"Records scraped: {len(all_tenders)}")
        print(f"Output file: {OUTPUT_FILE}")
        print(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            driver.quit()
        # Save whatever we have
        if all_tenders:
            save_to_csv(all_tenders, OUTPUT_FILE)


if __name__ == "__main__":
    main()
