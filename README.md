# grume — Gmail → AI → Canva 自動化

Gmailに写真と店舗情報を送るだけで、**画像整理 → Web調査 → Markdown生成 → Canva作成・保存 → 完了メール返信**までを自動化するプロジェクトです。

## 自動フロー

```text
Gmail
  ↓
添付写真 / 店舗名 / コース名 / 料理順を取得
  ↓
OpenAI Vision
  ├─ 外観 / 店内 / 乾杯 / 料理 / 焼き工程 / アップを分類
  └─ 指定されたコース順に並び替え
  ↓
OpenAI Web Search
  └─ 公式情報を優先して店舗を調査
  ↓
post.md + post.json
  ├─ 表紙コピー
  ├─ 各ページ文章
  └─ 強い表現の重複チェック
  ↓
Canva MCP exact edit
  ├─ MASTERテンプレートをコピー
  ├─ Gmail写真をCanvaへアップロード
  ├─ 既存の背景写真を update_fill で置換
  ├─ 既存テキストを replace_text で置換
  └─ commit-editing-transaction で自動保存
  ↓
Gmailへ完成Canva URLを返信
```

## なぜ Canva MCP を優先するのか

既存の「蟹かに城」型テンプレートでは、料理写真が通常の画像要素ではなく**ページ背景**として入っています。

Canva Autofillは背景そのものを画像フィールドとして扱えないため、このプロジェクトではデフォルトを:

```env
CANVA_MODE=mcp
```

にしています。

Canva MCP の編集トランザクションを使うと、既存レイアウトを崩さず、背景画像そのものを差し替えられます。

```text
copy-design
→ start-editing-transaction
→ update_fill / replace_text
→ commit-editing-transaction
```

Autofill用に作り直したテンプレートを使う場合のみ:

```env
CANVA_MODE=autofill
```

も利用できます。

## メール形式

件名:

```text
[グルメCanva] 焼肉しょうちゃん天満
```

本文例:

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

写真を1〜20枚添付します。iPhoneのHEIC/HEIFもJPEGへ自動変換します。

## 投稿ルール

`config/gourmet_rules.yaml` に固定しています。

- 写真主役
- 短文
- 話し言葉
- 絵文字あり
- 未確認情報を捏造しない
- コース順を最優先
- 「優勝すぎる」「ビジュやばすぎる」「反則級」などの強い表現を重複させない
- 自動検証に失敗したら1回コピーを再生成
- 料理名に確信がない場合は要確認扱い

## セットアップ

### Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## 1. Gmail OAuth

Google CloudでGmail APIを有効化し、OAuth Desktop Client JSONを:

```text
secrets/google_client_secret.json
```

へ保存します。

初回のみ:

```bash
python scripts/gmail_oauth_bootstrap.py
```

## 2. Canva REST OAuth

REST APIは、Gmailから取得したローカル写真をCanvaのAssetとしてアップロードするために使います。

必要スコープ:

```text
asset:read
asset:write
design:content:read
design:content:write
design:meta:read
```

初回のみ:

```bash
python scripts/canva_oauth_bootstrap.py
```

## 3. Canva MCP OAuth

正確なテンプレート編集には Canva MCP を使います。

```env
CANVA_MCP_SERVER_URL=https://mcp.canva.com/mcp
CANVA_MCP_CLIENT_ID=...
CANVA_MCP_CLIENT_SECRET=...
CANVA_MCP_REDIRECT_URI=http://127.0.0.1:8766/callback
```

初回のみ:

```bash
python scripts/canva_mcp_oauth_bootstrap.py
```

MCPのOAuthトークンは:

```text
secrets/canva_mcp_token.json
```

へ保存され、その後はrefresh tokenで自動更新します。

> Canva MCPを自作の外部AIアプリから利用するには、Canva側でそのOAuthクライアントのMCP利用が有効になっている必要があります。

## MASTER TEMPLATE

現在の既定値:

```env
CANVA_SOURCE_ID=DAHQmZ-GP3I
```

これは「蟹かに城」ベースの20ページテンプレートです。

テンプレート構造の識別ルールは:

```text
config/canva_template_profile.yaml
```

に保存しています。

ページ1:
- 📍 から始まるテキスト → 店名
- \ を含むテキスト → フック
- 日本橋 → 最寄駅
- 大阪 → エリア
- 残りの大きいテキスト → 表紙サブコピー

ページ2〜20:
- 各ページの唯一の非空キャプション → 本文

画像:
- 各ページのroot background fill → 投稿写真

このため、テンプレートの見た目を崩さず差し替えます。

## 実行

1回だけ:

```bash
python -m grume.worker once
```

60秒ごとにGmail監視:

```bash
python -m grume.worker loop --interval 60
```

Docker:

```bash
docker compose up -d --build
```

## Gmailラベル

自動作成:

- `grume/processing`
- `grume/done`
- `grume/error`

デフォルト検索:

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

## Canvaモード

### exact edit — 推奨

```env
CANVA_MODE=mcp
```

既存テンプレートをそのままコピーし、背景画像とテキストを直接差し替えます。

### Autofill — 代替

```env
CANVA_MODE=autofill
```

Canva側で画像・テキストをData autofillフィールドとして作り直したテンプレート用です。

### Canvaなし

```env
CANVA_MODE=off
```

調査・MD生成まで行います。

## 実装済み

- Gmail監視
- Gmail画像添付取得
- HEIC / HEIF対応
- AI画像分類
- コース順整理
- Web検索店舗調査
- 構造化コピー
- 強表現重複検査
- 自動再生成
- Markdown / JSON保存
- Canva REST asset upload
- Canva REST Autofill fallback
- Canva remote MCP接続
- MASTERコピー
- 背景画像直接置換
- テキスト直接置換
- Canva自動commit
- Canva完成URL取得
- Gmail完成通知
- Docker常駐運用
- pytest CI

## セキュリティ

以下はGitへコミットしないでください。

```text
.env
secrets/google_client_secret.json
secrets/google_token.json
secrets/canva_token.json
secrets/canva_mcp_token.json
```

本番では `secrets/` と `output/` を永続ボリュームにしてください。
