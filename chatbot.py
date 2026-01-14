# chatbot.py in your repo
import os
import requests

# These come from Cursor Secrets automatically!
API_KEY = os.environ.get('API_KEY')
BASE_URL = os.environ.get('BASE_URL')


def chat(message):
    """Send a message to the chat API and return the response."""
    if not BASE_URL:
        raise ValueError("BASE_URL environment variable is not set")
    if not API_KEY:
        raise ValueError("API_KEY environment variable is not set")
    
    response = requests.post(
        f"{BASE_URL}/agents",
        auth=(API_KEY, ""),
        json={
            "prompt": {"text": message},
            "source": {
                "repository": os.environ.get('GITHUB_REPO'),
                "ref": "main"
            }
        }
    )
    return response.json()


if __name__ == "__main__":
    try:
        result = chat("What is Python?")
        print(result)
    except ValueError as e:
        print(f"Configuration error: {e}")
    except requests.RequestException as e:
        print(f"Request error: {e}")
