from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailClient:
    def __init__(self, client_secret_file: str, token_file: str):
        self.client_secret_file = client_secret_file
        self.token_file = token_file
        self.service = build("gmail", "v1", credentials=self._credentials(), cache_discovery=False)

    def _credentials(self) -> Credentials:
        token_path = Path(self.token_file)
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def ensure_label(self, name: str) -> str:
        labels = self.service.users().labels().list(userId="me").execute().get("labels", [])
        for label in labels:
            if label.get("name") == name:
                return label["id"]
        created = self.service.users().labels().create(
            userId="me",
            body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        ).execute()
        return created["id"]

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        result = self.service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        return result.get("messages", [])

    def get_message(self, message_id: str) -> dict[str, Any]:
        return self.service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()

    def modify_labels(
        self,
        message_id: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> None:
        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": add or [], "removeLabelIds": remove or []},
        ).execute()

    def save_image_attachments(self, message: dict[str, Any], out_dir: Path) -> list[str]:
        out_dir.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []

        def walk(part: dict) -> None:
            filename = part.get("filename") or ""
            mime = part.get("mimeType") or ""
            attachment_id = part.get("body", {}).get("attachmentId")
            if filename and attachment_id and (
                mime.startswith("image/")
                or filename.lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"))
            ):
                data = self.service.users().messages().attachments().get(
                    userId="me", messageId=message["id"], id=attachment_id
                ).execute()["data"]
                padding = "=" * (-len(data) % 4)
                raw = base64.urlsafe_b64decode(data + padding)
                path = out_dir / filename
                path.write_bytes(raw)
                saved.append(str(path))
            for child in part.get("parts", []) or []:
                walk(child)

        walk(message.get("payload", {}))
        return saved

    def send_reply(self, to_email: str, subject: str, body: str, thread_id: str | None = None) -> None:
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        payload: dict[str, Any] = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        self.service.users().messages().send(userId="me", body=payload).execute()
