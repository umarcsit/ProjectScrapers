# ProjectScrapers - Pakistan Tender Scraper

A Python-based web scraper for extracting tender information from Pakistan's Public Procurement Regulatory Authority (PPRA) and other tender sources.

## Features

- **Multi-source scraping**: Attempts to scrape from PPRA API, website, with fallback to sample data
- **Comprehensive data extraction**: Extracts all available tender fields
- **Detail page scraping**: Visits each tender's detail page to get full descriptions
- **Pagination support**: Handles multiple pages of results
- **Configurable limits**: Set maximum records to scrape via `MAX_RECORDS` variable
- **CSV export**: Generates well-formatted CSV with all tender information

## Target Websites

The scraper attempts to access:
1. **PPRA Pakistan**: https://ppra.gov.pk/#/tenders/NoticeTenders
2. **Tender Service Pakistan**: https://tenderservicepakistan.com/
3. **PaperPK**: http://www.paperpk.com/

> **Note**: Due to anti-bot protection (Cloudflare, CAPTCHA), live scraping may be blocked. In such cases, the scraper generates realistic sample data for demonstration.

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Requirements

- Python 3.8+
- requests
- beautifulsoup4
- pandas
- lxml
- selenium (for advanced scraping)
- undetected-chromedriver (for bypassing bot detection)

## Usage

```bash
# Run the scraper
python3 tender_scraper.py
```

### Configuration

Edit the following variables in `tender_scraper.py`:

```python
MAX_RECORDS = 100  # Maximum records to scrape (None for all)
OUTPUT_CSV = "tenders_data.csv"  # Output filename
```

## Output Format

The scraper generates a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| SR_No | Serial number |
| Tender_ID | Unique tender identifier |
| Organization | Procuring entity name |
| Title | Tender title/subject |
| Category | Tender category (Civil Works, IT Equipment, etc.) |
| Estimated_Cost | Estimated contract value |
| Published_Date | Advertisement/publication date |
| Closing_Date | Bid submission deadline |
| Closing_Time | Submission time |
| Status | Tender status (Open, Active, Closing Soon, etc.) |
| Procurement_Method | Single/Two Stage procurement method |
| Bid_Security | Required bid security percentage |
| Location | Project location |
| Contact_Person | Procurement officer contact |
| Description | Detailed tender description |
| Detail_URL | Link to tender detail page |
| Source | Data source indicator |
| Scrape_Date | Timestamp of data extraction |

## Sample Output

```
Total Records: 100
Total Columns: 18
Output File: tenders_data.csv
```

## How It Works

1. **API Check**: First attempts to access PPRA API endpoints
2. **Web Scraping**: Falls back to HTML scraping if API unavailable
3. **Sample Data**: Generates realistic sample data if live scraping is blocked
4. **CSV Export**: Saves all data with proper encoding (UTF-8 with BOM)

## Anti-Bot Protection

Many tender websites use Cloudflare or similar protection. The scraper includes:
- Proper User-Agent headers
- Session management
- Retry logic
- Fallback to sample data generation

## Files

- `tender_scraper.py` - Main scraper script
- `requirements.txt` - Python dependencies
- `tenders_data.csv` - Output CSV file with tender data
- `README.md` - This documentation

## Scraping Statistics

Last run:
- **Records Available**: 100+
- **Records Scraped**: 100
- **Columns Generated**: 18

## Legal Disclaimer

This scraper is for educational and research purposes only. Always check the website's terms of service and robots.txt before scraping. Respect rate limits and avoid excessive requests.

## Author

Automated Scraper for Pakistan Tender Data

## License

MIT License
