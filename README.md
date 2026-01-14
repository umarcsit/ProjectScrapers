# ProjectScrapers

A collection of web scrapers for extracting data from various tender and procurement websites.

## Pakistan Tenders Scraper

### Description
This scraper extracts tender information from [TendersOnTime Pakistan Tenders](https://www.tendersontime.com/pakistan-tenders/). It collects data from the main listing page and visits each tender's detail page to extract comprehensive information.

### Features
- Scrapes tender listings from the main page
- Visits each tender's detail page to extract the `box_detail` content
- Handles pagination (if available)
- Configurable maximum records limit
- Polite scraping with configurable delays between requests
- Exports data to CSV format

### Output Columns (18 total)
| Column | Description |
|--------|-------------|
| Title | Tender title/name |
| TOT_Reference_No | TendersOnTime reference number |
| Country | Country where tender is located |
| Deadline | Tender submission deadline |
| Notice_Type | Type of notice (Tender, RFP, etc.) |
| Summary | Brief summary of the tender |
| Financier | Funding source |
| Purchaser_Ownership | Public/Private ownership |
| Tender_Value | Estimated tender value |
| Document_Ref_No | Document reference number |
| Purchaser_Name | Name of purchasing organization |
| Purchaser_Address | Address of purchaser |
| Description | Full description from detail page (`box_detail`) |
| Detail_URL | URL to the tender detail page |
| Detail_Scraped | Boolean indicating if detail page was scraped |
| Country_Detail | Country from detail page |
| Deadline_Detail | Deadline from detail page |
| TOT_Reference_Detail | Reference number from detail page |

### Installation

```bash
pip install requests beautifulsoup4 pandas lxml
```

### Usage

```bash
python3 pakistan_tenders_scraper.py
```

### Configuration
Edit the following variables at the top of `pakistan_tenders_scraper.py`:

```python
MAX_RECORDS = 50  # Maximum records to scrape (None for all)
DELAY_BETWEEN_REQUESTS = 1  # Seconds between requests
OUTPUT_CSV = "pakistan_tenders.csv"  # Output filename
```

### Sample Output
The scraper generates a CSV file with all tender information:

```
Total records scraped: 20
Total records available on website: 20
Columns in CSV: 18
```

### Notes
- The website currently displays ~20 tenders on the main Pakistan tenders page
- Some fields require login to view (marked as `[Login Required]`)
- The scraper respects rate limits with configurable delays
- Invalid/template entries are automatically filtered out

## Files
- `pakistan_tenders_scraper.py` - Main scraper script
- `pakistan_tenders.csv` - Output CSV with scraped data
