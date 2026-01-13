# ProjectScrapers

A collection of web scrapers for procurement and tender websites.

## GGGI Tender Scraper

Scrapes current tenders from the Global Green Growth Institute (GGGI) e-Green Procurement Portal.

**Source:** https://in-tendhost.co.uk/gggi/aspx/Tenders/Current

### Features

- Extracts all current tender listings
- Handles JavaScript-rendered content using Selenium
- Saves data to CSV format
- Extracts: ID, Title, Reference, Process Type, Closing Date, Timezone, and Detail Link

### Installation

```bash
pip install -r requirements.txt
```

**Note:** Chrome or Chromium browser must be installed on your system.

### Usage

```bash
python3 gggi_tender_scraper.py
```

This will:
1. Load the GGGI tender portal
2. Extract all current tender information
3. Save the results to `gggi_tenders.csv`

### Output Fields

| Field | Description |
|-------|-------------|
| ID | Unique tender identifier |
| Title | Tender title/name |
| Reference | Reference number |
| Process_Type | Type of procurement process (e.g., RFP) |
| Closing_Date | Application deadline |
| Timezone | Timezone for the deadline |
| Link | Direct link to tender details |

### Example Output

```csv
ID,Title,Reference,Process_Type,Closing_Date,Timezone,Link
2007,Capacity Development to Strengthen Electric Vehicle Testing in Nepal,1000NP-04,RFP,21 Jan 2026 16:00,UTC +09:00) Korea Standard Time,https://in-tendhost.co.uk/gggi/aspx/ProjectManage/2007
```

### Requirements

- Python 3.8+
- Chrome/Chromium browser
- See `requirements.txt` for Python dependencies
