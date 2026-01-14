# scraper.py - Basic web scraping utilities
import requests
from urllib.parse import urljoin, urlparse


def fetch_page(url, headers=None, timeout=30):
    """
    Fetch a web page and return its content.
    
    Args:
        url: The URL to fetch
        headers: Optional dictionary of HTTP headers
        timeout: Request timeout in seconds
    
    Returns:
        The response text content
    
    Raises:
        requests.RequestException: If the request fails
    """
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; ProjectScrapers/1.0)'
    }
    if headers:
        default_headers.update(headers)
    
    response = requests.get(url, headers=default_headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_links(html_content, base_url=None):
    """
    Extract all links from HTML content.
    
    Args:
        html_content: HTML string to parse
        base_url: Optional base URL to resolve relative links
    
    Returns:
        List of extracted URLs
    """
    import re
    
    # Simple regex to find href attributes
    href_pattern = r'href=["\']([^"\']+)["\']'
    links = re.findall(href_pattern, html_content, re.IGNORECASE)
    
    if base_url:
        links = [urljoin(base_url, link) for link in links]
    
    return links


def is_valid_url(url):
    """Check if a URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


if __name__ == "__main__":
    # Example usage
    test_url = "https://example.com"
    try:
        print(f"Fetching {test_url}...")
        content = fetch_page(test_url)
        print(f"Fetched {len(content)} characters")
        
        links = extract_links(content, test_url)
        print(f"Found {len(links)} links:")
        for link in links[:5]:  # Show first 5 links
            print(f"  - {link}")
    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
