# ADB Consulting Opportunities Scraper (CSRN)

A Python scraper to extract consulting services recruitment notices from the **Asian Development Bank (ADB)** Self-Service Portal.

## Source URL

```
https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN_HOME_PAGE
```

## Features

- Extracts comprehensive consulting opportunity data:
  - **Project Details**: ID, Title, Project Number
  - **Location**: Country, Region
  - **Type**: Firm or Individual consulting
  - **Terms**: Deadline, Duration, Budget Range
  - **Method**: Selection Method, Engagement Type
  - **Links**: Detail URL, Terms of Reference

- Automatic pagination handling
- Export to **JSON** and **CSV** formats
- Summary statistics and reporting

## Installation

```bash
pip install -r requirements.txt
```

## Requirements

- Python 3.7+
- selenium
- webdriver-manager
- beautifulsoup4
- Chrome browser installed

## Usage

### Command Line

```bash
python3 adb_scraper.py
```

### In Python

```python
from adb_scraper import ADBConsultingScraper

# Initialize scraper
scraper = ADBConsultingScraper(headless=True, delay=2.0)

# Scrape opportunities (max 10 pages)
opportunities = scraper.scrape_opportunities(max_pages=10)

# Save results
scraper.save_to_json("opportunities.json")
scraper.save_to_csv("opportunities.csv")

# Print summary
scraper.print_summary()
```

### Load Existing Data

```python
scraper = ADBConsultingScraper()
scraper.load_from_json("adb_consulting_opportunities.json")
scraper.print_summary()
```

## Output Format

### JSON Structure

```json
{
  "csrn_id": "12345",
  "title": "TA-6645 REG: Project Name - Consulting Package",
  "project_name": "Project Name",
  "project_number": "54087-001",
  "country": "Regional",
  "sector": "Finance",
  "consulting_type": "Firm",
  "engagement_type": "Full-time",
  "selection_method": "QCBS",
  "budget_range": "$100,000 - $500,000",
  "duration": "12 months",
  "deadline": "15-Jan-2026",
  "status": "Open",
  "detail_url": "https://www.adb.org/projects/54087-001/main",
  "scraped_at": "2026-01-12T15:00:00"
}
```

### CSV Columns

| Column | Description |
|--------|-------------|
| csrn_id | CSRN Reference ID |
| title | Full title of the opportunity |
| project_name | Project name |
| project_number | ADB Project Number |
| country | Country/Region |
| sector | Sector (Finance, Transport, etc.) |
| consulting_type | Firm or Individual |
| engagement_type | Type of engagement |
| selection_method | Selection method (QCBS, CQS, etc.) |
| budget_range | Budget range |
| duration | Expected duration |
| deadline | Submission deadline |
| status | Current status |
| detail_url | Link to full details |

## Project Types

The scraper recognizes these ADB project types:
- **LOAN**: Loan projects
- **GRANT**: Grant projects  
- **TA**: Technical Assistance

## Country Codes

Common ADB country codes:
- REG: Regional
- CAM: Cambodia
- PRC: China
- VIE: Vietnam
- IND: India
- INO: Indonesia
- PHI: Philippines
- BAN: Bangladesh
- PAK: Pakistan
- And more...

## Files

| File | Description |
|------|-------------|
| `adb_scraper.py` | Main scraper script |
| `adb_consulting_opportunities.json` | Scraped data (JSON) |
| `adb_consulting_opportunities.csv` | Scraped data (CSV) |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

## Troubleshooting

### Chrome Driver Issues
```bash
pip install webdriver-manager
```

### No Data Scraped
- Check if the URL is accessible in your browser
- Try running with `headless=False` to see the browser
- The page structure may have changed

## License

MIT License

## Disclaimer

This scraper is for educational and research purposes. Please respect ADB's terms of service and rate limits.
