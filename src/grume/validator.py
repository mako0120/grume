from __future__ import annotations

from pathlib import Path

import yaml

from .models import PostPackage


class PostValidator:
    def __init__(self, rules_path: str = "config/gourmet_rules.yaml"):
        self.rules = yaml.safe_load(Path(rules_path).read_text(encoding="utf-8"))

    def validate(self, post: PostPackage, filenames: set[str]) -> list[str]:
        errors: list[str] = []
        expressions: list[str] = self.rules.get("strong_expressions", [])
        max_chars = int(self.rules.get("style", {}).get("max_caption_chars", 90))
        seen_expression: dict[str, int] = {}
        seen_pages: set[int] = set()

        for page in post.pages:
            if page.page_index in seen_pages:
                errors.append(f"ページ番号重複: {page.page_index}")
            seen_pages.add(page.page_index)

            if page.filename not in filenames:
                errors.append(f"存在しない画像ファイル: {page.filename}")

            if len(page.text) > max_chars:
                errors.append(f"ページ{page.page_index}の本文が長すぎます: {len(page.text)}文字")

            for expression in expressions:
                if expression in page.text:
                    seen_expression[expression] = seen_expression.get(expression, 0) + 1

        for expression, count in seen_expression.items():
            if count > 1:
                errors.append(f"強い表現が重複: {expression} x{count}")

        if len(post.pages) > len(filenames):
            errors.append("ページ数が画像数を超えています")

        return errors
