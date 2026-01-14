# ProjectScrapers

Collection of web scrapers for procurement and tender portals.

## Punjab eProcurement Portal Scraper

**Source URL:** https://eproc.punjab.gov.pk/ActiveTenders.aspx

**Scraper File:** `eproc_punjab_gov_pk.py`

**Output CSV:** `eproc_punjab_gov_pk.csv`

### Features

- ✅ Extracts all tender information from the main listing page
- ✅ Visits each tender's detail page (View Details) for additional information
- ✅ Downloads and extracts text from PDF files (Tender Notice & Bidding Documents)
- ✅ Handles ASP.NET pagination to scrape all pages
- ✅ Configurable `MAX_RECORDS` variable to limit scraping
- ✅ Reports total available records
- ✅ Robust error handling and retry logic
- ✅ Rate limiting to be respectful to the server

### Installation

```bash
pip install -r requirements.txt
```

### Usage

```bash
python eproc_punjab_gov_pk.py
```

### Configuration

Edit the following variables in `eproc_punjab_gov_pk.py`:

```python
# Maximum records to scrape (set to None for all records)
MAX_RECORDS = None  # Change this to limit records, e.g., MAX_RECORDS = 100

# Request settings
REQUEST_TIMEOUT = 60
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds
DELAY_BETWEEN_REQUESTS = 2  # seconds to be polite to the server
```

### Output CSV Columns

The scraper generates a comprehensive CSV with the following columns:

#### Main Listing Columns
| Column | Description |
|--------|-------------|
| `sr_no` | Serial number |
| `procurement_name` | Name/title of the procurement |
| `procurement_name_link` | URL to tender detail page |
| `organization` | Procuring organization name |
| `tender_ref_no` | Tender reference number |
| `tender_notice` | Tender notice label |
| `tender_notice_pdf_link` | URL to tender notice PDF |
| `bidding_document` | Bidding document label |
| `bidding_document_pdf_link` | URL to bidding document PDF |
| `published_date` | Date tender was published |
| `closing_date` | Submission deadline date |
| `opening_date` | Bid opening date |
| `tender_value` | Estimated tender value |
| `tender_status` | Current status of tender |

#### Detail Page Columns
| Column | Description |
|--------|-------------|
| `detail_organization` | Organization from detail page |
| `detail_tender_type` | Type of tender/procurement |
| `detail_category` | Tender category |
| `detail_estimated_cost` | Estimated cost/value |
| `detail_earnest_money` | Earnest money/bid security amount |
| `detail_tender_fee` | Document fee |
| `detail_submission_deadline` | Submission deadline |
| `detail_opening_date` | Bid opening date |
| `detail_validity_period` | Bid validity period |
| `detail_contact_person` | Contact person name |
| `detail_contact_email` | Contact email address |
| `detail_contact_phone` | Contact phone number |
| `detail_address` | Organization address |
| `detail_eligibility_criteria` | Eligibility requirements |
| `detail_technical_specifications` | Technical specs |
| `detail_special_instructions` | Special instructions/remarks |

#### Description Columns
| Column | Description |
|--------|-------------|
| `description` | Combined description (from detail page + PDFs) |
| `tender_notice_pdf_text` | Extracted text from tender notice PDF |
| `bidding_document_pdf_text` | Extracted text from bidding document PDF |
| `detail_description` | Description from detail page |
| `detail_raw_content` | Full raw content from detail page |

### Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `pandas` - Data manipulation and CSV export
- `PyPDF2` - PDF text extraction (fallback)
- `pdfplumber` - PDF text extraction (primary)
- `lxml` - Fast HTML/XML parsing
- `urllib3` - URL handling

### Notes

- The scraper handles SSL certificate issues automatically
- PDF text extraction uses `pdfplumber` for better accuracy, with `PyPDF2` as fallback
- ASP.NET ViewState and pagination are handled automatically
- The `Description` column contains combined content from:
  1. Detail page description
  2. Tender notice PDF text
  3. Bidding document PDF text
