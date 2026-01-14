# chatbot.py in your repo
import os
import sys
import requests

# These come from Cursor Secrets automatically!
API_KEY = os.environ.get('API_KEY')
BASE_URL = os.environ.get('BASE_URL')

if not API_KEY or not BASE_URL:
    print("Error: API_KEY and BASE_URL environment variables must be set.")
    sys.exit(1)

def chat(message):
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
    result = chat("What is Python?")
    print(result)
