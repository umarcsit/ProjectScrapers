# ProjectScrapers

## GGGI Tender Scraper

A Python web scraper for extracting tender information from the Global Green Growth Institute (GGGI) e-Green Procurement Portal.

### Features

- Scrapes tenders from **Current**, **Forthcoming**, and **Awarded** pages
- Uses Selenium to render JavaScript-loaded content
- Visits each tender's detail page to extract comprehensive descriptions
- Exports all data to CSV format

### Output CSV Columns

| Column | Description |
|--------|-------------|
| mode | Tender type (Current/Forthcoming/Awarded) |
| reference | Tender reference number |
| title | Tender title |
| category | Procurement category (RFP, etc.) |
| **description** | Full description scraped from detail page |
| deadline | Submission deadline |
| published_date | Publication date |
| project_id | Internal project ID |
| detail_url | Link to tender detail page |

### Installation

```bash
pip install -r requirements.txt
```

### Usage

```bash
python3 gggi_tender_scraper.py
```

### Output

The scraper generates:
- `gggi_tenders_latest.csv` - Latest scraped data
- `gggi_tenders_YYYYMMDD_HHMMSS.csv` - Timestamped backup

### Source URL

https://in-tendhost.co.uk/gggi/aspx/Tenders/Current
