# ProjectScrapers

A collection of web scraping utilities and a chatbot integration.

## Features

- **scraper.py** - Basic web scraping utilities for fetching pages and extracting links
- **chatbot.py** - Integration with chat API using Cursor Secrets

## Usage

### Web Scraper

```python
from scraper import fetch_page, extract_links

# Fetch a web page
content = fetch_page("https://example.com")

# Extract links from HTML
links = extract_links(content, base_url="https://example.com")
```

### Chatbot

Set the required environment variables:
- `API_KEY` - Your API key
- `BASE_URL` - The base URL for the chat API
- `GITHUB_REPO` - (Optional) GitHub repository reference

```python
from chatbot import chat

result = chat("What is Python?")
print(result)
```

## Requirements

- Python 3.6+
- requests

## Installation

```bash
pip install requests
```
