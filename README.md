# ProjectScrapers

## Devex scraper

This repo includes a simple, **polite** Devex scraper that:

- fetches **public HTML pages**
- checks `robots.txt` by default
- extracts title/description/H1 + all links
- writes results as **JSONL** (one JSON object per line)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Usage

Scrape the homepage:

```bash
python devex_scraper.py --url "https://www.devex.com/" --max-pages 1 --out devex_home.jsonl
```

Discover and crawl internal links (bounded by `--max-pages`):

```bash
python devex_scraper.py --url "https://www.devex.com/" --discover --max-pages 5 --out devex_crawl.jsonl
```

If you get blocked or want to debug parsing, you can save a page to disk and parse it locally:

```bash
python devex_scraper.py --url "https://www.devex.com/" --html-file saved.html --max-pages 1
```

### Output format

Each line in the output file is a JSON object like:

- `url`
- `status_code`
- `title`
- `description`
- `h1`
- `canonical_url`
- `links` (deduplicated, normalized)
- `extracted_at_epoch_s`