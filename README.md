# ProjectScrapers - Pakistan Tender Scraper

A Python web scraper for extracting tender information from PPRA (Public Procurement Regulatory Authority) Pakistan.

## 📊 Scraping Results

**Website:** https://ppra.gov.pk/#/tenders/NoticeTenders

| Metric | Value |
|--------|-------|
| **Total Records Available** | ~10 (Notice Tenders section) |
| **Records Scraped** | 10 |
| **Output File** | `tenders_data.csv` |
| **Columns** | 10 |

> **Note:** The "Notice Tenders" section shows recent/active tender notices. The number varies as new tenders are published and old ones expire.

## 🎛️ Configuration

Edit `tender_scraper.py` to adjust:

```python
MAX_RECORDS = 50  # Maximum records to scrape. Set to None for ALL records.
OUTPUT_CSV = "tenders_data.csv"  # Output filename
```

## 📋 CSV Output Columns

| Column | Description |
|--------|-------------|
| SR_No | Serial number |
| Tender_No | Unique tender ID (e.g., TS847223E) |
| Organization | Procuring entity with location |
| Title | Tender title/subject |
| **Description** | Detailed tender description |
| Downloads | Available downloads |
| Advertisement_Date | Publication date |
| Closing_Date | Bid submission deadline |
| Page | Page number scraped from |
| Scrape_Date | Timestamp of extraction |

## 🚀 Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run scraper
python3 tender_scraper.py
```

## 📦 Requirements

- Python 3.8+
- undetected-chromedriver
- selenium
- pandas
- Google Chrome browser

## 📄 Sample Output

```
SR_No,Tender_No,Organization,Title,Description,Advertisement_Date,Closing_Date
1,TS847223E,"Sui Northern Gas Pipelines Limited,Lahore",Supply of 12 Dia..,Supply of 12 Dia..,"Jan 13, 2026","Jan 29, 2026"
2,TS847222E,"State Bank of Pakistan,Karachi central",Supply of Sweet Water...,Supply of Sweet Water...,"Jan 13, 2026","Feb 12, 2026"
```

## 🔧 How It Works

1. **Browser Automation**: Uses undetected-chromedriver to bypass bot detection
2. **Data Extraction**: Parses HTML tables to extract tender information
3. **Pagination**: Handles multiple pages automatically
4. **CSV Export**: Saves data with UTF-8 encoding

## ⚠️ Notes

- The PPRA "Notice Tenders" section displays recent active notices
- Total records vary based on current tender activity
- `MAX_RECORDS` variable controls scraping limit
- Scraper respects website structure and doesn't overload servers

## 📁 Files

- `tender_scraper.py` - Main scraper script
- `requirements.txt` - Python dependencies
- `tenders_data.csv` - Scraped tender data
- `README.md` - Documentation

## 📜 License

MIT License - For educational and research purposes.
