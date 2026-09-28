# grume — Gmail → AI → Canva 自動化

写真付きメールを送るだけで、**店舗調査 → Markdown生成 → Canva生成 → 保存 → 完了メール返信**まで自動化するMVPです。

## 完成フロー

```text
Gmail
  ↓
添付写真・店舗名・コース情報を取得
  ↓
OpenAI Visionで写真を分類・コース順に整理
  ↓
OpenAI Web Searchで店舗を調査
  ↓
グルメ日誌ルールで post.md / post.json を生成
  ↓
Canvaへ画像アップロード
  ↓
Autofill対応 MASTER TEMPLATE に流し込み
  ↓
新しいCanvaデザインを保存
  ↓
完成URLをGmailで返信
```

## メールの送り方

件名:

```text
[グルメCanva] 焼肉しょうちゃん天満
```

本文:

```text
店舗名：焼肉しょうちゃん天満
コース：粋コース
エリア：天満

料理：
・キムチ盛り合わせ
・和風ナムル
・和牛炙りユッケ
・厚切りタンブリアン
・チシャ
・厳選赤身2種
・厳選ホルモン2種
・豪快特上ハラミ
・こだわり和風冷麺

メモ：
・タンとハラミを強めに推したい
・強い表現は被らせない
```

写真を添付してください。本文が簡単でも、件名から店舗名を補完します。

## グルメ日誌ルール

- 写真主役
- 短文・話し言葉・絵文字あり
- 未確認情報を捏造しない
- 強い表現を同一投稿内で重複させない
- コース順が本文にある場合は最優先
- 料理名の確信度が低い場合は `needs_review`
- 既存Canvaテンプレのレイアウトを維持し、中身だけ差し替える

## セットアップ

### Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

### Gmail OAuth

Google CloudでGmail APIを有効化し、OAuth Desktop Client JSONを:

```text
secrets/google_client_secret.json
```

へ保存。

初回だけ:

```bash
python scripts/gmail_oauth_bootstrap.py
```

生成される `secrets/google_token.json` はGitに入れません。

### Canva OAuth

Canva Developer PortalでOutside CanvaのOAuth設定を作成し、少なくとも以下のスコープを許可:

```text
asset:write
design:content:write
design:meta:read
```

Brand Templateを使う場合は追加:

```text
brandtemplate:content:read
```

初回だけ:

```bash
python scripts/canva_oauth_bootstrap.py
```

Canvaのaccess tokenは短命で、refresh tokenは更新時にローテーションされます。本アプリは `CANVA_TOKEN_FILE` を自動更新するため、Docker/VPSでは **secretsディレクトリを永続化**してください。

## Canva MASTER TEMPLATE

CanvaのData autofillで、MASTER TEMPLATEの要素に以下のフィールド名を設定します。

```text
STORE_NAME
AREA
STATION
COVER_SUBCOPY
COVER_HOOK

PAGE_01_IMAGE
PAGE_01_TEXT
PAGE_02_IMAGE
PAGE_02_TEXT
...
PAGE_20_IMAGE
PAGE_20_TEXT
```

既存デザインを元にする場合:

```env
CANVA_SOURCE_TYPE=design
CANVA_SOURCE_ID=DAxxxxxxxxx
```

Brand Templateの場合:

```env
CANVA_SOURCE_TYPE=brand_template
CANVA_SOURCE_ID=DAxxxxxxxxx
```

## 実行

1回だけ:

```bash
python -m grume.worker once
```

常時監視:

```bash
python -m grume.worker loop --interval 60
```

Docker:

```bash
docker compose up -d --build
```

## Gmailラベル

自動作成・管理:

- `grume/processing`
- `grume/done`
- `grume/error`

デフォルト対象:

```text
is:unread has:attachment subject:"[グルメCanva]"
```

## 出力

```text
output/
  20260928_191800_store/
    job.json
    image_plan.json
    research.md
    research.json
    post.md
    post.json
    canva_result.json
```

画像は実行時に使用しますがGitには含めません。

## 実装済み

- Gmail添付写真取得
- HEIC/HEIF → JPEG変換
- AIによる写真分類/並べ替え
- Web検索付き店舗リサーチ
- 構造化コピー生成
- 強表現重複チェック + 1回自動修正
- MD/JSON保存
- Canva Asset Upload
- Canva Dataset検証
- Canva Autofill
- Canva OAuth refresh tokenローテーション保存
- Gmail完成通知
- 失敗ラベル付与
- pytest CI

## 重要

このMVPは **常駐サーバー/VPS/Docker** で動かす前提です。GitHub Actionsの定期実行だけでCanvaのrefresh tokenを安全に永続更新する設計にはしていません。
