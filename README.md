# ProjectScrapers

Web scrapers for extracting tender/procurement information from various sources.

## GGGI Tender Scraper

Comprehensive scraper for the Global Green Growth Institute (GGGI) e-Green Procurement Portal.

**Source URL:** https://in-tendhost.co.uk/gggi/aspx/Tenders/Current

### Features

- Extracts ALL current tenders from the GGGI portal
- Visits each tender's detail page to get comprehensive information
- Extracts full tender descriptions (up to 10,000 characters)
- Saves results to a comprehensive CSV file
- Uses Selenium for JavaScript-rendered content
- Handles dynamic page loading with retry logic

### Output CSV Columns

The generated `gggi_tenders.csv` file includes:

| Column | Description |
|--------|-------------|
| Title | Full tender title/name |
| Project_ID | GGGI internal project identifier |
| Reference | Tender reference number (e.g., 1000NP-04) |
| Process | Procurement process type (e.g., RFP) |
| Issue_Date | Date the tender was published |
| Deadline_Date | Submission deadline date and time |
| Deadline_Full | Complete deadline information with timezone |
| Deadline_For_Applications | Application deadline |
| Timezone | Timezone for deadlines (e.g., Korea Standard Time) |
| Description | Comprehensive description including background, objectives, scope, requirements (up to 10,000 chars) |
| Attachment | Available document attachments |
| Detail_URL | URL to full tender details page |
| Detail_Status | Whether detail page was successfully scraped |
| Additional columns | Any other fields extracted from tender pages |

### Sample Tenders Extracted

The scraper extracts tenders such as:
- Capacity Development to Strengthen Electric Vehicle Testing in Nepal
- Capacity Enhancement in Estimation and Valuation of Natural Resource Abundance
- Conceptual Site Development Plan, environmental and social impact assessment
- Consulting Firm for Development of Renewable Energy projects
- Pacific Regional Scoping Study and Analysis of Rural Electrification
- Pre-feasibility Study for Ground Mounted Solar Farm with Battery Storage
- Provision of Services for Private Sector Engagement
- Technical Assessment for Selected Investment Proposals

### Requirements

```bash
pip install -r requirements.txt
```

**Dependencies:**
- requests>=2.28.0
- beautifulsoup4>=4.11.0
- lxml>=4.9.0
- selenium>=4.15.0
- webdriver-manager>=4.0.0

### Usage

```bash
python tender_scraper.py
```

The scraper will:
1. Load the GGGI tender listing page (with retry logic)
2. Extract all current tenders with basic information
3. Navigate to each tender's detail page
4. Extract comprehensive descriptions and all available fields
5. Save everything to `gggi_tenders.csv`

### Output Files

- `gggi_tenders.csv` - Comprehensive CSV with all tender information
- `raw_listing_page.html` - Debug file with listing page HTML (created during run)
- `raw_detail_page.html` - Debug file with first detail page HTML (created during run)

### Technical Notes

- Uses Chrome in headless mode via Selenium
- Includes rate limiting (3 second delay between requests)
- Handles JavaScript-rendered dynamic content
- Retries page loads on failure
- Extracts up to 10,000 characters for description field
- Cleans and normalizes all text content

### Example Output

```
GGGI COMPREHENSIVE TENDER SCRAPER
Started: 2026-01-16 10:46:00

Loading GGGI Tender Listing Page
  Page loaded successfully!
Found 10 tender rows
Extracted 10 tenders

Scraping Detail Pages
[1/10] Scraping detail for Project 2007
  Title: Capacity Development to Strengthen Electric Vehicl...
  Extracted 12 fields, Description: 10000 chars
...

SAVED: gggi_tenders.csv
Tenders: 10
Columns: 16
```
