import requests
from bs4 import BeautifulSoup
import sys

def scrape_devex():
    url = "https://www.devex.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print(f"Page Title: {soup.title.string.strip() if soup.title else 'No Title Found'}")
        
        # Try to find some headlines - inspecting common tags used for headlines
        print("\nPossible Headlines:")
        headlines = soup.find_all(['h1', 'h2', 'h3'])
        for i, headline in enumerate(headlines[:10], 1):
            text = headline.get_text(strip=True)
            if text:
                print(f"{i}. {text}")
                
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    scrape_devex()
