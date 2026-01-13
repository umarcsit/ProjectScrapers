# ProjectScrapers

A collection of web scrapers for extracting tender/procurement information.

## GGGI Tender Scraper

Scrapes current tenders from the Global Green Growth Institute (GGGI) portal at [in-tendhost.co.uk](https://in-tendhost.co.uk/gggi/aspx/Tenders/Current).

### Prerequisites

- Python 3.8+
- Chrome browser installed

### Installation

```bash
pip install -r requirements.txt
```

### Usage

**Note:** The GGGI tender portal requires authentication. You'll need valid login credentials.

1. Set your credentials as environment variables:

```bash
export GGGI_EMAIL='your-email@example.com'
export GGGI_PASSWORD='your-password'
```

2. Run the scraper:

```bash
python3 gggi_tender_scraper.py
```

3. The scraper will:
   - Login to the portal
   - Navigate to the current tenders page
   - Extract tender information
   - Save results to a CSV file (e.g., `gggi_tenders_20240115_120000.csv`)

### Output

The scraper exports tender data to a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| title | Tender title/name |
| reference | Reference number |
| deadline | Submission deadline |
| category | Tender category/type |
| status | Current status |
| description | Brief description |
| url | Link to tender details |

### Example Output

```
============================================================
GGGI Tender Scraper
============================================================
Loading https://in-tendhost.co.uk/gggi/aspx/Tenders/Current...
Found 5 tenders.

Tenders Found:
------------------------------------------------------------

1. Consultancy for Climate Finance Project
   Reference: GGGI-2024-001
   Deadline: 2024-02-15
   URL: https://in-tendhost.co.uk/gggi/...

Saved 5 tenders to gggi_tenders_20240115_120000.csv
```

### Programmatic Usage

```python
from gggi_tender_scraper import GGGITenderScraper

# Initialize with credentials
scraper = GGGITenderScraper(
    email='your-email@example.com',
    password='your-password',
    headless=True  # Set to False to see browser
)

# Scrape tenders
tenders = scraper.scrape()

# Save to CSV
scraper.save_to_csv(tenders, 'output.csv')

# Or process programmatically
for tender in tenders:
    print(f"{tender.title} - Deadline: {tender.deadline}")
```

## License

MIT
