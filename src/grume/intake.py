from __future__ import annotations

import base64
import re
from email.utils import parseaddr

from .models import EmailJob


def decode_gmail_body(payload: dict) -> str:
    texts: list[str] = []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if mime == "text/plain" and data:
            padding = "=" * (-len(data) % 4)
            texts.append(base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="ignore"))
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return "\n".join(texts).strip()


def parse_email_job(message: dict, image_paths: list[str]) -> EmailJob:
    payload = message.get("payload", {})
    headers = {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}
    subject = headers.get("subject", "")
    sender = parseaddr(headers.get("from", ""))[1] or headers.get("from", "")
    body = decode_gmail_body(payload)

    store_name = ""
    course_name = None
    area = None
    dishes: list[str] = []
    notes: list[str] = []
    section: str | None = None

    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("店舗名：") or line.startswith("店舗名:"):
            store_name = re.split(r"[：:]", line, maxsplit=1)[1].strip()
            section = None
        elif line.startswith("コース：") or line.startswith("コース:"):
            course_name = re.split(r"[：:]", line, maxsplit=1)[1].strip() or None
            section = None
        elif line.startswith("エリア：") or line.startswith("エリア:"):
            area = re.split(r"[：:]", line, maxsplit=1)[1].strip() or None
            section = None
        elif line.rstrip("：:") == "料理":
            section = "dishes"
        elif line.rstrip("：:") == "メモ":
            section = "notes"
        elif line.startswith(("・", "-", "•")):
            value = line[1:].strip()
            if section == "dishes":
                dishes.append(value)
            else:
                notes.append(value)
        elif section == "dishes":
            dishes.append(line)
        elif section == "notes":
            notes.append(line)

    if not store_name:
        match = re.search(r"\[グルメCanva\]\s*(.+)$", subject)
        if match:
            store_name = match.group(1).strip()

    if not store_name:
        raise ValueError("店舗名を取得できません。件名を [グルメCanva] 店舗名 にするか、本文に店舗名：を入れてください。")

    return EmailJob(
        message_id=message["id"],
        thread_id=message.get("threadId"),
        sender=sender,
        subject=subject,
        store_name=store_name,
        course_name=course_name,
        area=area,
        dishes=dishes,
        notes=notes,
        image_paths=image_paths,
    )
