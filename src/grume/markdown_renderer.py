from __future__ import annotations

from .models import EmailJob, ImagePlan, PostPackage, ResearchedStore


def render_post_markdown(
    job: EmailJob,
    plan: ImagePlan,
    research: ResearchedStore,
    post: PostPackage,
) -> str:
    lines = [
        f"# {post.store_name}",
        "",
        "## 基本情報",
        f"- 店舗名: {post.store_name}",
        f"- コース: {job.course_name or ''}",
        f"- エリア: {post.area}",
        f"- 最寄駅: {post.nearest_station or ''}",
        f"- 要確認: {'YES' if post.needs_review or plan.needs_review else 'NO'}",
        "",
        "## 表紙",
        f"- サブコピー: {post.cover_subcopy}",
        f"- フック: {post.cover_hook}",
        "",
        "## 検証済み情報",
    ]
    lines.extend(f"- {fact}" for fact in research.verified_facts)
    lines.extend(["", "## ページ"])
    for page in sorted(post.pages, key=lambda p: p.page_index):
        lines.extend(
            [
                f"### PAGE_{page.page_index:02d}",
                f"- image: {page.filename}",
                f"- dish: {page.dish_name or ''}",
                f"- text: {page.text}",
                "",
            ]
        )

    if research.caution_notes:
        lines.extend(["## 注意事項"])
        lines.extend(f"- {note}" for note in research.caution_notes)
        lines.append("")

    if post.review_reasons:
        lines.extend(["## REVIEW"])
        lines.extend(f"- {reason}" for reason in post.review_reasons)
        lines.append("")

    return "\n".join(lines)
