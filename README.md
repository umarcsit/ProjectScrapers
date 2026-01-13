# ProjectScrapers

A collection of web scrapers for extracting public procurement data.

## PPRA Pakistan Tenders Scraper

Scrapes active tender information from the Public Procurement Regulatory Authority (PPRA) Pakistan website.

### Features

- Extracts tender information from https://ppra.gov.pk/#/tenders/activetenders
- Handles dynamic SPA content using Playwright
- Paginates through all available tenders
- Outputs data to CSV format

### Requirements

```bash
pip install playwright requests
python -m playwright install chromium
```

### Usage

```bash
python ppra_scraper.py
```

### Output

The scraper generates `ppra_active_tenders.csv` with the following columns:

| Column | Description |
|--------|-------------|
| tender_no | Tender reference number |
| title | Tender title/description |
| organization | Procuring agency/organization |
| status | Tender status |
| closing_date | Submission deadline |

### Sample Output

The scraper successfully extracts 1000+ active tenders from the PPRA portal.

### Notes

- The website uses Angular SPA with dynamic content loading
- Data is extracted from DOM elements after JavaScript rendering
- Rate limiting is implemented to avoid overloading the server

## Files

- `ppra_scraper.py` - Main scraper script
- `ppra_active_tenders.csv` - Scraped tender data
- `chatbot.py` - Example chatbot script (unrelated)

## License

MIT
