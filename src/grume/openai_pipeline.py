from __future__ import annotations

import base64
import json
from pathlib import Path

from openai import OpenAI

from .models import EmailJob, ImagePlan, PostPackage, ResearchedStore


class AIPipeline:
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    @staticmethod
    def _image_data_url(path: str) -> str:
        raw = Path(path).read_bytes()
        return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")

    def plan_images(self, job: EmailJob) -> ImagePlan:
        content: list[dict] = [
            {
                "type": "input_text",
                "text": (
                    "あなたはグルメInstagramカルーセルの写真編集者です。"
                    "添付写真を1枚ずつ識別し、自然な投稿順に並べてください。"
                    "本文に料理順がある場合は最優先してください。"
                    "外観/店内/乾杯/料理/焼き工程/アップ/締めを考慮してください。"
                    "料理名を断定できない場合はdish_nameをnullにしconfidenceを下げてください。"
                    f"\n店舗名: {job.store_name}"
                    f"\nコース: {job.course_name or ''}"
                    f"\n料理順: {job.dishes}"
                    f"\nファイル名順: {[Path(p).name for p in job.image_paths]}"
                ),
            }
        ]
        for path in job.image_paths:
            content.append(
                {
                    "type": "input_image",
                    "image_url": self._image_data_url(path),
                    "detail": "high",
                }
            )

        response = self.client.responses.parse(
            model=self.model,
            input=[{"role": "user", "content": content}],
            text_format=ImagePlan,
        )
        plan = response.output_parsed
        if plan is None:
            raise RuntimeError("画像解析の構造化出力を取得できませんでした。")
        return plan

    def research_store(self, job: EmailJob) -> tuple[str, ResearchedStore]:
        prompt = f"""
店舗をWebで調査してください。

店舗名: {job.store_name}
エリアヒント: {job.area or ''}
コース名: {job.course_name or ''}
ユーザーが示した料理: {job.dishes}

調査優先順位:
1. 公式サイト
2. 公式Instagram
3. Google Maps等の店舗情報
4. 食べログ等の補助情報

目的:
Instagram/Canva投稿に使える正確な店舗情報を得ること。
住所、最寄駅、ジャンル、店舗の特徴、コース/料理に関係する確認可能な事実を整理してください。
営業時間・価格・定休など変動しやすい情報は、今回の投稿文に必須でなければ無理に断定しないでください。
最後に参照URLを列挙してください。
"""
        researched = self.client.responses.create(
            model=self.model,
            tools=[{"type": "web_search", "search_context_size": "medium"}],
            input=prompt,
        )
        raw = researched.output_text

        parsed = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "次の調査結果を、与えられたスキーマに厳密に整理してください。"
                        "確認できない内容はnullまたはcaution_notesへ。捏造禁止。"
                    ),
                },
                {"role": "user", "content": raw},
            ],
            text_format=ResearchedStore,
        )
        store = parsed.output_parsed
        if store is None:
            raise RuntimeError("店舗調査の構造化に失敗しました。")
        return raw, store

    def write_post(
        self,
        job: EmailJob,
        plan: ImagePlan,
        research: ResearchedStore,
        default_area: str,
        repair_feedback: list[str] | None = None,
    ) -> PostPackage:
        plan_json = json.dumps(plan.model_dump(), ensure_ascii=False)
        research_json = json.dumps(research.model_dump(), ensure_ascii=False)
        feedback = "\n".join(repair_feedback or [])
        prompt = f"""
あなたは「グルメ日誌｜大阪」のCanva投稿コピー担当です。

ルール:
- 日本語
- 写真主役
- 1ページ1メッセージ
- 短く、話し言葉、絵文字は自然に
- 強い表現は投稿内で同じものを繰り返さない
- 「優勝すぎる」「ビジュやばすぎる」「反則級」「止まらん」「たまらん」「えぐい」などを必要に応じて分散
- 未確認の味や料理名を捏造しない
- ユーザーが料理順を指定した場合はその順番を守る
- ファイル名はImagePlanに存在する名前をそのまま使用
- pagesには使用する全写真を1回ずつ含める
- page_index=1は表紙画像。page_indexは1から連番にする
- ページ数は写真数を超えない
- 表紙は店舗名とは別に、短いサブコピーと短いフックを作る
- areaは {job.area or research.area or default_area}

店舗:
{job.model_dump_json(indent=2)}

画像計画:
{plan_json}

調査:
{research_json}

前回検証エラー:
{feedback}
"""
        response = self.client.responses.parse(
            model=self.model,
            input=[{"role": "user", "content": prompt}],
            text_format=PostPackage,
        )
        post = response.output_parsed
        if post is None:
            raise RuntimeError("投稿コピーの構造化出力に失敗しました。")
        return post
