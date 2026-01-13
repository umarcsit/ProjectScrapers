# ProjectScrapers

A collection of web scrapers for extracting tender/procurement information.

## GGGI Tender Scraper

Scrapes current tenders from the Global Green Growth Institute (GGGI) portal at [in-tendhost.co.uk](https://in-tendhost.co.uk/gggi/aspx/Tenders/Current).

### Features

- Extracts all tenders from the listing page
- **Visits each tender's detail page** to extract comprehensive information
- Exports data to CSV with **31 columns** of information
- Handles JavaScript-rendered content with Selenium

### Prerequisites

- Python 3.8+
- Chrome browser installed

### Installation

```bash
pip install -r requirements.txt
```

### Usage

```bash
python3 gggi_tender_scraper.py
```

### Output Columns

The scraper extracts the following information for each tender:

| Category | Fields |
|----------|--------|
| **Basic Info** | title, reference, process_type, project_id |
| **Dates** | timezone, issue_date, deadline, questions_deadline |
| **Organization** | buyer, buyer_contact, buyer_email, buyer_phone |
| **Classification** | status, category, cpv_codes |
| **Location** | location, region, country |
| **Financial** | estimated_value, currency, duration |
| **Details** | description, scope_of_work, eligibility, submission_requirements, evaluation_criteria |
| **Documents** | documents, attachments |
| **Other** | detail_url, site_visit, additional_info |

### Example Output

```
======================================================================
GGGI Tender Scraper - Full Data Extraction
======================================================================
Loading https://in-tendhost.co.uk/gggi/aspx/Tenders/Current...

Processing page 1...
  Found 10 tenders, 10 project IDs

Extracting detail page information...

[1/10] Capacity Development to Strengthen Electric Vehicle Testing in Nepal
[2/10] Capacity Enhancement in Estimation and Valuation...
...

Saved 10 tenders to gggi_tenders_20260113_082559.csv

Total tenders: 10
Total columns: 31
```

### Sample CSV Data

```csv
title,reference,process_type,timezone,issue_date,deadline,description,...
"Capacity Development...",1000NP-04,RFP,(UTC +09:00) Korea Standard Time,19 Dec 2025,22 Jan 2026,"GGGI Nepal Country Office is inviting...",...
```

### Programmatic Usage

```python
from gggi_tender_scraper import GGGITenderScraper, Tender

# Initialize scraper
scraper = GGGITenderScraper(headless=True)

# Scrape all tenders with details
tenders = scraper.scrape()

# Save to CSV
scraper.save_to_csv(tenders, 'output.csv')

# Process programmatically
for tender in tenders:
    print(f"Title: {tender.title}")
    print(f"Reference: {tender.reference}")
    print(f"Deadline: {tender.deadline}")
    print(f"Description: {tender.description[:200]}...")
    print("---")
```

### Dependencies

- `selenium` - Browser automation
- `webdriver-manager` - Chrome driver management
- `beautifulsoup4` - HTML parsing
- `requests` - HTTP requests

## License

MIT
