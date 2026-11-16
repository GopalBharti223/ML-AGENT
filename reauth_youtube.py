"""Re-authenticate YouTube OAuth using client_secret.json.
Run this script to open browser login and generate a fresh youtube_token.json.
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = "youtube_token.json"

if not os.path.exists(CLIENT_SECRET_FILE):
    print("❌ Missing client_secret.json!")
    exit(1)

print("🌐 Starting Google OAuth authentication flow...")
flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

with open(TOKEN_FILE, "w", encoding="utf-8") as f:
    f.write(creds.to_json())

print("✅ Fresh OAuth token successfully saved to youtube_token.json!")
