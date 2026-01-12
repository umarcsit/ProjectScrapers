# ADB Projects Scraper

A Python scraper to extract project information from the **Asian Development Bank (ADB)** website.

## Features

- Extracts comprehensive project data including:
  - Project ID, Title, Country, Region
  - Sector, Subsector, Status
  - Approval/Signing/Closing dates
  - Financing amount, Borrower
  - Executing/Implementing agencies
  - Project description and objectives

- Multiple data access methods:
  1. **Selenium scraping** (with Cloudflare bypass)
  2. **CSV import** from ADB Data Library
  3. **JSON import** from previous scrapes

- Exports to both **JSON** and **CSV** formats

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python3 adb_scraper.py
```

### In Python

```python
from adb_scraper import ADBScraper

# Initialize scraper
scraper = ADBScraper(headless=True, delay=2.0)

# Method 1: Scrape with Selenium
projects = scraper.scrape_with_selenium(max_pages=5, fetch_details=True)

# Method 2: Load from downloaded CSV
projects = scraper.load_from_csv('adb_sovereign_projects.csv')

# Method 3: Load from JSON
projects = scraper.load_from_json('adb_projects.json')

# Save results
scraper.save_to_json('adb_projects.json')
scraper.save_to_csv('adb_projects.csv')

# Print summary
scraper.print_summary()
```

### Scrape a Single Project

```python
scraper = ADBScraper()
project = scraper.scrape_project_by_id('56789')
print(project)
```

## Cloudflare Protection Note

The ADB website uses Cloudflare protection that may block automated access from cloud servers. If you encounter this:

### Option 1: Download Data Manually
Visit these ADB Data Library URLs in your browser:

1. **Sovereign Projects**: https://data.adb.org/dataset/sovereign-projects-loans-grants-and-technical-assistance
2. **Nonsovereign Operations**: https://data.adb.org/dataset/nonsovereign-operations
3. **Cofinancing**: https://data.adb.org/dataset/adb-official-cofinancing
4. **Procurement**: https://data.adb.org/dataset/contracts-goods-works-and-services

Then load the CSV:
```python
scraper.load_from_csv('downloaded_file.csv')
```

### Option 2: Run Locally
The scraper works better from a local machine (not cloud servers).

### Option 3: Use VPN
Connect via VPN to a different IP address.

## Output Format

### JSON Structure
```json
{
  "project_id": "56789",
  "title": "Infrastructure Development Project",
  "country": "Philippines",
  "region": "Southeast Asia",
  "sector": "Transport",
  "status": "Active",
  "approval_date": "2023-06-15",
  "financing_amount": "$250 million",
  "project_url": "https://www.adb.org/projects/56789",
  ...
}
```

### CSV Columns
| Column | Description |
|--------|-------------|
| project_id | ADB Project Number |
| title | Project Name |
| country | Country/Countries |
| region | Geographic Region |
| sector | Primary Sector |
| subsector | Subsector |
| status | Project Status |
| project_type | Type of Project |
| modality | Financing Modality |
| approval_date | Board Approval Date |
| signing_date | Loan Signing Date |
| closing_date | Expected Closing |
| financing_amount | ADB Financing |
| borrower | Borrower Name |
| executing_agency | Executing Agency |
| description | Project Description |
| project_url | ADB Project Page URL |

## Requirements

- Python 3.7+
- requests
- beautifulsoup4
- selenium
- undetected-chromedriver
- Chrome or Firefox browser

## Files

- `adb_scraper.py` - Main scraper script
- `adb_projects.json` - Scraped data in JSON format
- `adb_projects.csv` - Scraped data in CSV format
- `requirements.txt` - Python dependencies

## License

MIT License
