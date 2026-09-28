from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

CLIENT_SECRET = Path("secrets/google_client_secret.json")
TOKEN = Path("secrets/google_token.json")

if not CLIENT_SECRET.exists():
    raise SystemExit(
        "secrets/google_client_secret.json がありません。Google Cloud の OAuth Desktop Client JSON を配置してください。"
    )

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
TOKEN.parent.mkdir(parents=True, exist_ok=True)
TOKEN.write_text(creds.to_json(), encoding="utf-8")
print(f"Saved: {TOKEN}")
