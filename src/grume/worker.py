from __future__ import annotations

import argparse
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from slugify import slugify

from .canva_client import CanvaClient
from .gmail_client import GmailClient
from .image_utils import normalize_image
from .intake import parse_email_job
from .markdown_renderer import render_post_markdown
from .openai_pipeline import AIPipeline
from .settings import Settings
from .validator import PostValidator


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class Worker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.gmail = GmailClient(
            settings.google_oauth_client_secret_file,
            settings.google_oauth_token_file,
        )
        self.ai = AIPipeline(settings.openai_api_key, settings.openai_model)
        self.validator = PostValidator()

        self.processing_label = self.gmail.ensure_label(settings.gmail_processing_label)
        self.done_label = self.gmail.ensure_label(settings.gmail_done_label)
        self.error_label = self.gmail.ensure_label(settings.gmail_error_label)

        self.canva = None
        if (
            settings.canva_client_id
            and settings.canva_client_secret
            and settings.canva_source_id
        ):
            self.canva = CanvaClient(
                api_base=settings.canva_api_base,
                client_id=settings.canva_client_id,
                client_secret=settings.canva_client_secret,
                token_file=settings.canva_token_file,
                source_type=settings.canva_source_type,
                source_id=settings.canva_source_id,
            )

    def process_message(self, message_id: str) -> Path:
        message = self.gmail.get_message(message_id)
        self.gmail.modify_labels(message_id, add=[self.processing_label])

        temp = self.settings.output_path / "_tmp" / message_id
        if temp.exists():
            shutil.rmtree(temp)
        temp.mkdir(parents=True, exist_ok=True)

        try:
            attachments = self.gmail.save_image_attachments(message, temp / "raw")
            if not (self.settings.min_images <= len(attachments) <= self.settings.max_images):
                raise ValueError(
                    f"画像数が範囲外です: {len(attachments)} "
                    f"(許可 {self.settings.min_images}〜{self.settings.max_images})"
                )

            provisional = parse_email_job(message, attachments)
            slug = slugify(provisional.store_name, allow_unicode=False) or "store"
            job_dir = (
                self.settings.output_path
                / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slug}"
            )
            image_dir = job_dir / "images"
            image_dir.mkdir(parents=True, exist_ok=True)

            normalized = [str(normalize_image(path, image_dir)) for path in attachments]
            job = provisional.model_copy(update={"image_paths": normalized})

            plan = self.ai.plan_images(job)
            raw_research, research = self.ai.research_store(job)
            post = self.ai.write_post(
                job,
                plan,
                research,
                default_area=self.settings.default_area,
            )

            filenames = {Path(path).name for path in normalized}
            validation = self.validator.validate(post, filenames)
            if validation:
                repaired = self.ai.write_post(
                    job,
                    plan,
                    research,
                    default_area=self.settings.default_area,
                    repair_feedback=validation,
                )
                validation = self.validator.validate(repaired, filenames)
                post = repaired

            reasons = list(post.review_reasons)
            reasons.extend(validation)
            if plan.needs_review and plan.review_reason:
                reasons.append(plan.review_reason)
            if reasons:
                post = post.model_copy(
                    update={"needs_review": True, "review_reasons": sorted(set(reasons))}
                )

            job_dir.mkdir(parents=True, exist_ok=True)
            write_json(job_dir / "job.json", job.model_dump())
            write_json(job_dir / "image_plan.json", plan.model_dump())
            (job_dir / "research.md").write_text(raw_research, encoding="utf-8")
            write_json(job_dir / "research.json", research.model_dump())
            write_json(job_dir / "post.json", post.model_dump())
            (job_dir / "post.md").write_text(
                render_post_markdown(job, plan, research, post),
                encoding="utf-8",
            )

            canva_result = None
            if self.canva:
                image_paths_by_name = {Path(p).name: p for p in normalized}
                canva_result = self.canva.create_autofilled_design(
                    title=post.design_title,
                    store_name=post.store_name,
                    area=post.area,
                    station=post.nearest_station,
                    cover_subcopy=post.cover_subcopy,
                    cover_hook=post.cover_hook,
                    pages=[p.model_dump() for p in post.pages],
                    image_paths_by_name=image_paths_by_name,
                )
                write_json(job_dir / "canva_result.json", canva_result)

            reply_lines = [
                "グルメCanva自動処理が完了しました。",
                "",
                f"店舗: {post.store_name}",
                f"要確認: {'あり' if post.needs_review else 'なし'}",
            ]
            if canva_result:
                edit_url = canva_result.get("urls", {}).get("edit_url") or canva_result.get("url")
                view_url = canva_result.get("urls", {}).get("view_url")
                if edit_url:
                    reply_lines.append(f"Canva編集: {edit_url}")
                if view_url:
                    reply_lines.append(f"Canva表示: {view_url}")
            else:
                reply_lines.append("Canva: 未設定のためMD生成まで完了")

            if post.review_reasons:
                reply_lines.extend(["", "要確認理由:"])
                reply_lines.extend(f"- {reason}" for reason in post.review_reasons)

            self.gmail.send_reply(
                to_email=job.sender,
                subject=f"[グルメCanva 完成] {post.store_name}",
                body="\n".join(reply_lines),
                thread_id=job.thread_id,
            )

            self.gmail.modify_labels(
                message_id,
                add=[self.done_label],
                remove=[self.processing_label, "UNREAD"],
            )
            return job_dir

        except Exception:
            self.gmail.modify_labels(
                message_id,
                add=[self.error_label],
                remove=[self.processing_label],
            )
            raise
        finally:
            if temp.exists():
                shutil.rmtree(temp, ignore_errors=True)

    def run_once(self) -> list[Path]:
        results: list[Path] = []
        for item in self.gmail.search(self.settings.gmail_query, max_results=5):
            message_id = item["id"]
            try:
                results.append(self.process_message(message_id))
            except Exception:
                logging.exception("message failed: %s", message_id)
        return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["once", "loop", "message"])
    parser.add_argument("--interval", type=int)
    parser.add_argument("--message-id")
    args = parser.parse_args()

    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    worker = Worker(settings)

    if args.mode == "once":
        worker.run_once()
    elif args.mode == "message":
        if not args.message_id:
            raise SystemExit("--message-id is required")
        worker.process_message(args.message_id)
    else:
        interval = args.interval or settings.poll_interval_seconds
        while True:
            worker.run_once()
            time.sleep(interval)


if __name__ == "__main__":
    main()
