from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ.get("CANVA_MCP_CLIENT_ID") or os.environ.get("CANVA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("CANVA_MCP_CLIENT_SECRET") or os.environ.get("CANVA_CLIENT_SECRET")
REDIRECT_URI = os.environ.get(
    "CANVA_MCP_REDIRECT_URI",
    "http://127.0.0.1:8766/callback",
)
TOKEN_FILE = Path(
    os.environ.get("CANVA_MCP_TOKEN_FILE", "secrets/canva_mcp_token.json")
)

AUTH_URL = "https://mcp.canva.com/authorize"
TOKEN_URL = "https://mcp.canva.com/token"

if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit(
        "CANVA_MCP_CLIENT_ID / CANVA_MCP_CLIENT_SECRET を設定してください。"
    )

verifier = secrets.token_urlsafe(72)
challenge = base64.urlsafe_b64encode(
    hashlib.sha256(verifier.encode("ascii")).digest()
).decode("ascii").rstrip("=")
state = secrets.token_urlsafe(32)

parsed = urlparse(REDIRECT_URI)
result: dict[str, str] = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        result["code"] = params.get("code", [""])[0]
        result["state"] = params.get("state", [""])[0]
        result["error"] = params.get("error", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            "Canva MCP authorization received. You can close this tab.".encode("utf-8")
        )

    def log_message(self, format, *args):
        return


server = HTTPServer(
    (parsed.hostname or "127.0.0.1", parsed.port or 8766),
    Handler,
)
thread = threading.Thread(target=server.handle_request, daemon=True)
thread.start()

query = {
    "code_challenge": challenge,
    "code_challenge_method": "S256",
    "response_type": "code",
    "client_id": CLIENT_ID,
    "state": state,
    "redirect_uri": REDIRECT_URI,
}
url = AUTH_URL + "?" + urlencode(query)
print("Canva MCP access must already be enabled for this OAuth client.")
print("Open this URL if the browser does not open automatically:\n")
print(url)
webbrowser.open(url)

thread.join(timeout=300)
server.server_close()

if result.get("error"):
    raise SystemExit(f"Canva MCP authorization failed: {result['error']}")
if not result.get("code"):
    raise SystemExit("Authorization code was not received.")
if result.get("state") != state:
    raise SystemExit("State mismatch. Aborting.")

response = requests.post(
    TOKEN_URL,
    auth=(CLIENT_ID, CLIENT_SECRET),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={
        "grant_type": "authorization_code",
        "code_verifier": verifier,
        "code": result["code"],
        "redirect_uri": REDIRECT_URI,
    },
    timeout=30,
)
response.raise_for_status()
token = response.json()
token["obtained_at"] = int(time.time())
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
TOKEN_FILE.write_text(
    json.dumps(token, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"Saved: {TOKEN_FILE}")
