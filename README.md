# ProjectScrapers

A collection of web scrapers for procurement and tender information.

## UNGM Tender Scraper

A comprehensive web scraper for the UN Global Marketplace (UNGM) tender notices.

### Features

- Scrapes tender information from https://www.ungm.org/Public/Notice
- Handles infinite scroll pagination to load all records
- Visits each tender's detail page to extract full descriptions
- Extracts comprehensive information including:
  - Notice ID, Title, Reference
  - UN Organization
  - Published Date, Deadline
  - Tender Type (RFP, RFQ, EOI, etc.)
  - Country and Beneficiary Country
  - Contact Information (Name, Email)
  - UNSPSC Codes
  - Attached Documents
  - Full Description
- Exports data to CSV format
- Configurable MAX_RECORDS limit
- Progress saving during scraping

### Requirements

```bash
pip install selenium webdriver-manager beautifulsoup4 pandas lxml
```

Chrome browser must be installed.

### Configuration

Edit `ungm_scraper.py` to configure:

```python
# Maximum records to scrape (set to None for all available)
MAX_RECORDS = 50

# Output file name
OUTPUT_FILE = "ungm_tenders.csv"

# Request delay between pages (seconds)
REQUEST_DELAY = 2
```

### Usage

```bash
python3 ungm_scraper.py
```

### Output

The scraper generates a CSV file (`ungm_tenders.csv`) with the following columns:

| Column | Description |
|--------|-------------|
| Notice_ID | Unique identifier for the tender |
| Title | Tender title |
| Reference | Reference number |
| UN_Organization | UN Agency (UNDP, UNICEF, WFP, etc.) |
| Published_Date | Publication date |
| Deadline | Submission deadline |
| Type | Tender type (RFP, RFQ, ITB, EOI, etc.) |
| Country | Country location |
| Sustainability | Sustainability badge (Yes/No) |
| Beneficiary_Country | Target beneficiary country |
| Contact_Name | Contact person information |
| Contact_Email | Contact email address |
| Contact_Address | Contact address |
| UNSPSC_Codes | UN Standard Products and Services Codes |
| Documents | List of attached documents |
| Description | Full tender description |
| Detail_URL | Link to tender detail page |

### Sample Output

The scraper will display progress and summary:

```
============================================================
SUMMARY
============================================================
Total records available on UNGM: 926
Records scraped: 50
Output file: ungm_tenders.csv
============================================================
```

### Notes

- The UNGM website uses infinite scroll, which the scraper handles automatically
- Rate limiting (REQUEST_DELAY) is implemented to be respectful to the server
- Progress is saved every 10 records to prevent data loss
- A log file (`ungm_scraper.log`) is generated for debugging

### License

MIT License
