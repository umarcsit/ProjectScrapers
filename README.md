# ProjectScrapers

A collection of web scrapers for extracting tender/procurement information from various sources.

## GGGI Tender Scraper

Scrapes tender information from the Global Green Growth Institute (GGGI) e-Green Procurement Portal.

**Source URL:** https://in-tendhost.co.uk/gggi/aspx/Tenders/Current

### Features

- Extracts all current tenders from the GGGI portal
- Visits each tender's detail page to get comprehensive descriptions
- Saves results to a CSV file with all available information
- Uses Selenium for JavaScript-rendered content

### Output Columns

The generated CSV file (`gggi_tenders.csv`) includes the following columns:

| Column | Description |
|--------|-------------|
| Title | Tender title/name |
| Project_ID | Unique project identifier |
| Reference | Tender reference number |
| Process | Type of process (e.g., RFP) |
| Deadline | Submission deadline with timezone |
| Description | Detailed description from the tender detail page |
| Detail_URL | URL to the full tender details |
| Detail_Page_Scraped | Whether the detail page was successfully scraped |
| Additional columns | Various other fields extracted from the detail pages |

### Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

Dependencies:
- requests
- beautifulsoup4
- lxml
- selenium
- webdriver-manager

### Usage

Run the scraper:

```bash
python tender_scraper.py
```

The scraper will:
1. Load the GGGI tender listing page
2. Extract all current tenders with their basic information
3. Visit each tender's detail page to extract descriptions
4. Save all data to `gggi_tenders.csv`

### Output

- `gggi_tenders.csv` - CSV file containing all scraped tender information

### Notes

- The scraper uses Chrome in headless mode via Selenium
- Rate limiting is implemented (2 second delay between detail page requests)
- The website uses JavaScript to render content, so Selenium is required
