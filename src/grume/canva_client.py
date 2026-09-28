from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import requests


class CanvaError(RuntimeError):
    pass


class CanvaClient:
    """Canva REST client.

    Used for local image uploads in both modes, and for Autofill as a fallback.
    """

    def __init__(
        self,
        api_base: str,
        client_id: str,
        client_secret: str,
        token_file: str,
        source_type: str,
        source_id: str,
    ):
        self.api_base = api_base.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = Path(token_file)
        self.source_type = source_type
        self.source_id = source_id

    def _load_token(self) -> dict:
        if not self.token_file.exists():
            raise CanvaError(
                f"Canva REST token file not found: {self.token_file}. "
                "Run scripts/canva_oauth_bootstrap.py first."
            )
        return json.loads(self.token_file.read_text(encoding="utf-8"))

    def _save_token(self, token: dict) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding="utf-8")

    def _refresh(self, refresh_token: str) -> dict:
        response = requests.post(
            f"{self.api_base}/oauth/token",
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            timeout=30,
        )
        if response.status_code >= 400:
            raise CanvaError(f"Canva REST token refresh failed: {response.status_code} {response.text}")
        token = response.json()
        token["obtained_at"] = int(time.time())
        self._save_token(token)
        return token

    def access_token(self) -> str:
        token = self._load_token()
        access = token.get("access_token")
        obtained = int(token.get("obtained_at", 0))
        expires_in = int(token.get("expires_in", 0))
        if access and obtained and expires_in and time.time() < obtained + expires_in - 300:
            return access
        refresh = token.get("refresh_token")
        if not refresh:
            if access:
                return access
            raise CanvaError("Canva REST access_token / refresh_token がありません")
        return self._refresh(refresh)["access_token"]

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token()}"}

    def upload_asset(self, image_path: str) -> str:
        path = Path(image_path)
        display_name = path.name[:50]
        name_b64 = base64.b64encode(display_name.encode("utf-8")).decode("ascii")
        headers = self._auth_headers() | {
            "Content-Type": "application/octet-stream",
            "Asset-Upload-Metadata": json.dumps({"name_base64": name_b64}),
        }
        with path.open("rb") as fh:
            response = requests.post(
                f"{self.api_base}/asset-uploads",
                headers=headers,
                data=fh,
                timeout=120,
            )
        if response.status_code >= 400:
            raise CanvaError(f"Canva asset upload start failed: {response.status_code} {response.text}")
        job_id = response.json()["job"]["id"]
        return self._poll_asset(job_id)

    def _poll_asset(self, job_id: str, timeout_seconds: int = 120) -> str:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            response = requests.get(
                f"{self.api_base}/asset-uploads/{job_id}",
                headers=self._auth_headers(),
                timeout=30,
            )
            if response.status_code >= 400:
                raise CanvaError(f"Canva asset upload poll failed: {response.status_code} {response.text}")
            job = response.json()["job"]
            if job["status"] == "success":
                return job["asset"]["id"]
            if job["status"] == "failed":
                raise CanvaError(f"Canva asset upload failed: {job.get('error')}")
            time.sleep(1.5)
        raise CanvaError(f"Canva asset upload timed out: {job_id}")

    def get_dataset(self) -> dict:
        if self.source_type == "design":
            url = f"{self.api_base}/designs/{self.source_id}/dataset"
        elif self.source_type == "brand_template":
            url = f"{self.api_base}/brand-templates/{self.source_id}/dataset"
        else:
            raise CanvaError(f"Unsupported CANVA_SOURCE_TYPE: {self.source_type}")
        response = requests.get(url, headers=self._auth_headers(), timeout=30)
        if response.status_code >= 400:
            raise CanvaError(f"Canva dataset failed: {response.status_code} {response.text}")
        return response.json().get("dataset", {})

    def create_autofilled_design(
        self,
        title: str,
        store_name: str,
        area: str,
        station: str | None,
        cover_subcopy: str,
        cover_hook: str,
        pages: list[dict],
        image_paths_by_name: dict[str, str],
    ) -> dict:
        dataset = self.get_dataset()
        if not dataset:
            raise CanvaError(
                "Canva source has no autofill dataset. "
                "Autofill mode requires explicit image/text data fields."
            )

        data: dict = {}

        def add_text(field: str, text: str) -> None:
            if field in dataset:
                data[field] = {"type": "text", "text": text}

        add_text("STORE_NAME", store_name)
        add_text("AREA", area)
        add_text("STATION", station or "")
        add_text("COVER_SUBCOPY", cover_subcopy)
        add_text("COVER_HOOK", cover_hook)

        uploaded: dict[str, str] = {}
        for page in pages:
            index = int(page["page_index"])
            filename = page["filename"]
            image_field = f"PAGE_{index:02d}_IMAGE"
            text_field = f"PAGE_{index:02d}_TEXT"
            add_text(text_field, page["text"])

            if image_field in dataset and filename in image_paths_by_name:
                if filename not in uploaded:
                    uploaded[filename] = self.upload_asset(image_paths_by_name[filename])
                data[image_field] = {"type": "image", "asset_id": uploaded[filename]}

        if not data:
            raise CanvaError("Autofill対象フィールドが1つも一致しませんでした。")

        body: dict = {"title": title, "data": data}
        if self.source_type == "design":
            body |= {"type": "create_from_design", "design_id": self.source_id}
        else:
            body |= {
                "type": "create_from_brand_template",
                "brand_template_id": self.source_id,
            }

        response = requests.post(
            f"{self.api_base}/autofills",
            headers=self._auth_headers() | {"Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        if response.status_code >= 400:
            raise CanvaError(f"Canva autofill start failed: {response.status_code} {response.text}")

        job_id = response.json()["job"]["id"]
        return self._poll_autofill(job_id)

    def _poll_autofill(self, job_id: str, timeout_seconds: int = 180) -> dict:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            response = requests.get(
                f"{self.api_base}/autofills/{job_id}",
                headers=self._auth_headers(),
                timeout=30,
            )
            if response.status_code >= 400:
                raise CanvaError(f"Canva autofill poll failed: {response.status_code} {response.text}")
            job = response.json()["job"]
            if job["status"] == "success":
                return job["result"]["design"]
            if job["status"] == "failed":
                raise CanvaError(f"Canva autofill failed: {job.get('error')}")
            time.sleep(2)
        raise CanvaError(f"Canva autofill timed out: {job_id}")
