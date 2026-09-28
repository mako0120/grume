from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import requests
import yaml
from agents.mcp import MCPServerStreamableHttp

from .canva_client import CanvaClient, CanvaError
from .models import PostPackage


class CanvaMcpError(CanvaError):
    pass


class CanvaMcpTokenStore:
    """Persistent OAuth token store for https://mcp.canva.com/mcp.

    Canva MCP uses per-user OAuth. The refresh token is persisted because
    the worker runs unattended after the user's one-time authorization.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_file: str,
        token_url: str = "https://mcp.canva.com/token",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = Path(token_file)
        self.token_url = token_url

    def _load(self) -> dict:
        if not self.token_file.exists():
            raise CanvaMcpError(
                f"Canva MCP token file not found: {self.token_file}. "
                "Run scripts/canva_mcp_oauth_bootstrap.py after MCP access is enabled."
            )
        return json.loads(self.token_file.read_text(encoding="utf-8"))

    def _save(self, token: dict) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(
            json.dumps(token, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _refresh(self, refresh_token: str) -> dict:
        response = requests.post(
            self.token_url,
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise CanvaMcpError(
                f"Canva MCP token refresh failed: {response.status_code} {response.text}"
            )
        token = response.json()
        # Some OAuth servers return a new rotating refresh token, others omit it.
        # Preserve the previous one only when a replacement wasn't supplied.
        token.setdefault("refresh_token", refresh_token)
        token["obtained_at"] = int(time.time())
        self._save(token)
        return token

    def access_token(self) -> str:
        token = self._load()
        access = token.get("access_token")
        obtained = int(token.get("obtained_at", 0))
        expires_in = int(token.get("expires_in", 0))
        if access and (not expires_in or time.time() < obtained + expires_in - 300):
            return access

        refresh = token.get("refresh_token")
        if not refresh:
            if access:
                return access
            raise CanvaMcpError("Canva MCP access_token / refresh_token がありません")
        return self._refresh(refresh)["access_token"]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True)
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _tool_payload(result: Any) -> dict:
    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = getattr(result, "structuredContent", None)
    if structured:
        value = _jsonable(structured)
        if isinstance(value, dict):
            return value

    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise CanvaMcpError("Canva MCP tool returned no JSON payload")


def _region_text(richtext: dict) -> str:
    return "".join(
        region.get("text", "")
        for region in richtext.get("regions", [])
        if region.get("type") == "character"
    ).strip()


class CanvaMcpEditor:
    """Exact-template editor.

    Unlike Canva Autofill, this edits the copied template's existing background
    fills directly. That is important for the current gourmet templates, where
    the photo is the page background rather than a normal image element.
    """

    def __init__(
        self,
        server_url: str,
        token_store: CanvaMcpTokenStore,
        rest_client: CanvaClient,
        source_design_id: str,
        template_profile_path: str,
    ):
        self.server_url = server_url
        self.token_store = token_store
        self.rest_client = rest_client
        self.source_design_id = source_design_id
        self.profile = yaml.safe_load(
            Path(template_profile_path).read_text(encoding="utf-8")
        )

    @staticmethod
    def _resolve_tool(available: set[str], logical: str) -> str:
        normalized = logical.replace("_", "-")
        for candidate in available:
            if candidate.replace("_", "-") == normalized:
                return candidate
        raise CanvaMcpError(f"Canva MCP tool is unavailable: {logical}")

    @staticmethod
    def build_operations(
        transaction: dict,
        post: PostPackage,
        asset_ids_by_filename: dict[str, str],
        profile: dict,
    ) -> list[dict]:
        pages = transaction.get("pages", [])
        fills = transaction.get("fills", [])
        richtexts = transaction.get("richtexts", [])

        page_ids: dict[int, str] = {}
        for i, page in enumerate(pages, start=1):
            page_number = int(page.get("page_number") or i)
            page_ids[page_number] = page["page_id"]

        operations: list[dict] = [
            {"type": "update_title", "title": post.design_title}
        ]

        # Replace page background fills. Prefer the root page fill whose
        # element_id equals page_id; it is exactly how the current templates
        # represent the photo background.
        for page in sorted(post.pages, key=lambda p: p.page_index):
            asset_id = asset_ids_by_filename.get(page.filename)
            if not asset_id:
                raise CanvaMcpError(f"No uploaded Canva asset for {page.filename}")
            candidates = [
                fill for fill in fills
                if int(fill.get("page_index", -1)) == page.page_index
                and fill.get("type") == "image"
                and fill.get("editable", True)
            ]
            if not candidates:
                raise CanvaMcpError(
                    f"No editable image fill on Canva page {page.page_index}"
                )
            page_id = page_ids.get(page.page_index)
            background = next(
                (fill for fill in candidates if fill.get("element_id") == page_id),
                candidates[0],
            )
            operations.append(
                {
                    "type": "update_fill",
                    "element_id": background["element_id"],
                    "asset_type": "image",
                    "asset_id": asset_id,
                    "alt_text": page.dish_name or post.store_name,
                }
            )

        # Page 1: use stable semantic hints from the source template.
        first_page = [
            rt for rt in richtexts
            if int(rt.get("page_index", -1)) == 1 and _region_text(rt)
        ]
        hints = profile.get("page1", {})

        def find(predicate, label: str) -> dict:
            matches = [rt for rt in first_page if predicate(rt, _region_text(rt))]
            if len(matches) != 1:
                raise CanvaMcpError(
                    f"Could not uniquely identify page-1 text element: {label} "
                    f"(matches={len(matches)})"
                )
            return matches[0]

        store_rt = find(
            lambda _rt, text: text.startswith(hints.get("store_prefix", "📍")),
            "store",
        )
        hook_rt = find(
            lambda _rt, text: hints.get("hook_contains", "\\") in text,
            "hook",
        )
        station_source = hints.get("station_source_text", "")
        area_source = hints.get("area_source_text", "")
        station_rt = find(
            lambda _rt, text: text == station_source,
            "station",
        )
        area_rt = find(
            lambda _rt, text: text == area_source,
            "area",
        )

        excluded = {
            store_rt["element_id"],
            hook_rt["element_id"],
            station_rt["element_id"],
            area_rt["element_id"],
        }
        subcopy_candidates = [
            rt for rt in first_page if rt["element_id"] not in excluded
        ]
        if len(subcopy_candidates) != 1:
            # Prefer the lower half / largest remaining text block.
            subcopy_candidates.sort(
                key=lambda rt: (
                    rt.get("containerElement", {}).get("position", {}).get("top", 0),
                    len(_region_text(rt)),
                ),
                reverse=True,
            )
        if not subcopy_candidates:
            raise CanvaMcpError("Could not identify page-1 subcopy")
        subcopy_rt = subcopy_candidates[0]

        hook_text = post.cover_hook.strip()
        if not (hook_text.startswith("\\") and hook_text.endswith("/")):
            clean_hook = hook_text.strip("\\/")
            hook_text = "\\" + clean_hook + "/"

        operations.extend(
            [
                {
                    "type": "replace_text",
                    "element_id": store_rt["element_id"],
                    "text": f"📍{post.store_name}",
                },
                {
                    "type": "replace_text",
                    "element_id": subcopy_rt["element_id"],
                    "text": post.cover_subcopy,
                },
                {
                    "type": "replace_text",
                    "element_id": hook_rt["element_id"],
                    "text": hook_text,
                },
                {
                    "type": "replace_text",
                    "element_id": station_rt["element_id"],
                    "text": post.nearest_station or "",
                },
                {
                    "type": "replace_text",
                    "element_id": area_rt["element_id"],
                    "text": post.area,
                },
            ]
        )

        # Pages 2..N: current template has exactly one non-empty caption richtext.
        for page in sorted(post.pages, key=lambda p: p.page_index):
            if page.page_index == 1:
                continue
            candidates = [
                rt for rt in richtexts
                if int(rt.get("page_index", -1)) == page.page_index
                and _region_text(rt)
            ]
            if len(candidates) != 1:
                raise CanvaMcpError(
                    f"Expected one caption on page {page.page_index}, "
                    f"found {len(candidates)}"
                )
            operations.append(
                {
                    "type": "replace_text",
                    "element_id": candidates[0]["element_id"],
                    "text": page.text,
                }
            )

        return operations

    async def _render_async(
        self,
        post: PostPackage,
        image_paths_by_name: dict[str, str],
    ) -> dict:
        token = self.token_store.access_token()
        server = MCPServerStreamableHttp(
            name="Canva",
            params={
                "url": self.server_url,
                "headers": {"Authorization": f"Bearer {token}"},
                "timeout": 60,
                "sse_read_timeout": 180,
            },
            cache_tools_list=True,
            use_structured_content=True,
            max_retry_attempts=2,
        )

        async with server:
            tools = await server.list_tools()
            available = {tool.name for tool in tools}

            copy_tool = self._resolve_tool(available, "copy-design")
            start_tool = self._resolve_tool(available, "start-editing-transaction")
            perform_tool = self._resolve_tool(available, "perform-editing-operations")
            commit_tool = self._resolve_tool(available, "commit-editing-transaction")
            cancel_tool = self._resolve_tool(available, "cancel-editing-transaction")
            get_design_tool = self._resolve_tool(available, "get-design")

            copy_payload = _tool_payload(
                await server.call_tool(
                    copy_tool,
                    {
                        "design_id": self.source_design_id,
                        "user_intent": (
                            f"{post.store_name}のグルメ投稿をMASTERテンプレートから作成"
                        ),
                    },
                )
            )
            design = (
                copy_payload.get("design")
                or copy_payload.get("design_summary")
                or copy_payload
            )
            design_id = design.get("id")
            if not design_id:
                raise CanvaMcpError(f"copy-design returned no design id: {copy_payload}")

            start_payload = _tool_payload(
                await server.call_tool(
                    start_tool,
                    {
                        "design_id": design_id,
                        "user_intent": (
                            "写真・店舗名・表紙コピー・各ページ本文を自動差し替え"
                        ),
                    },
                )
            )
            transaction = start_payload.get("transaction", {})
            transaction_id = transaction.get("id") or start_payload.get("transaction_id")
            if not transaction_id:
                raise CanvaMcpError(
                    f"start-editing-transaction returned no transaction id: {start_payload}"
                )

            try:
                # Upload local Gmail images with REST because Canva MCP's public
                # upload tool only accepts public HTTPS URLs.
                asset_ids: dict[str, str] = {}
                for page in post.pages:
                    if page.filename not in image_paths_by_name:
                        raise CanvaMcpError(
                            f"Post refers to missing local image: {page.filename}"
                        )
                    if page.filename not in asset_ids:
                        asset_ids[page.filename] = self.rest_client.upload_asset(
                            image_paths_by_name[page.filename]
                        )

                operations = self.build_operations(
                    start_payload,
                    post,
                    asset_ids,
                    self.profile,
                )

                pages_arg = start_payload.get("pages")
                perform_args: dict[str, Any] = {
                    "transaction_id": transaction_id,
                    "operations": operations,
                    "page_index": 1,
                    "user_intent": (
                        "MASTERテンプレートを維持し、写真と文章を投稿データに差し替える"
                    ),
                }
                if pages_arg:
                    perform_args["pages"] = pages_arg

                performed = _tool_payload(
                    await server.call_tool(perform_tool, perform_args)
                )
                failures = [
                    result
                    for result in performed.get("edit_operation_results", [])
                    if result.get("status") == "failure"
                ]
                if failures:
                    raise CanvaMcpError(
                        "Canva edit operation failed: "
                        + json.dumps(failures, ensure_ascii=False)
                    )

                committed = _tool_payload(
                    await server.call_tool(
                        commit_tool,
                        {
                            "transaction_id": transaction_id,
                            "user_intent": "自動生成したグルメ投稿をCanvaへ保存",
                        },
                    )
                )

                final_design = _tool_payload(
                    await server.call_tool(
                        get_design_tool,
                        {
                            "design_id": design_id,
                            "user_intent": "保存後のCanvaデザインURLを取得",
                        },
                    )
                )
                final = final_design.get("design") or final_design
                final["_commit"] = committed
                final["_mode"] = "mcp_exact_edit"
                return final
            except Exception:
                try:
                    await server.call_tool(
                        cancel_tool,
                        {
                            "transaction_id": transaction_id,
                            "user_intent": "自動編集失敗のためドラフト変更を破棄",
                        },
                    )
                except Exception:
                    pass
                raise

    def render(
        self,
        post: PostPackage,
        image_paths_by_name: dict[str, str],
    ) -> dict:
        return asyncio.run(self._render_async(post, image_paths_by_name))
