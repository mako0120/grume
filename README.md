# grume — ChatGPT グルメ自動制作ルール / MD保管庫

このリポジトリは **実行プログラムではありません**。

Gmailで受け取ったグルメ素材を、ChatGPTの自動化が処理するときに参照するルールと、完成した投稿Markdownを保存するための保管庫です。

## 実行主体

```text
Gmail
  ↓
ChatGPT Automation
  ├─ 対象メールを検知
  ├─ 添付写真を確認
  ├─ Webで店舗を調査
  ├─ 投稿MDを作成
  ├─ Canvaテンプレートをコピー
  ├─ 写真・文章を差し替え
  └─ Canvaを保存
  ↓
GitHub
  └─ 完成MD / 制作記録を保存
```

**GitHub Actions / OpenAI API / Gmail API / Canva API を動かすためのリポジトリではありません。**

以前作ったAPI実行コードはGit履歴には残っていますが、現在の運用では使用しません。

## ディレクトリ

```text
automation/
  chatgpt-task.md
  workflow.md

rules/
  gourmet-canva.md
  gmail-intake.md
  research.md
  md-storage.md

canva/
  templates.md

templates/
  post-template.md
  processing-record-template.md

posts/
  README.md
  INDEX.md
  YYYY/
    MM/
      YYYY-MM-DD_店舗名/
        post.md
        record.md
```

## 投稿制作の基準

基準Canva:

- 焼肉 城と七宝 — `DAHRTs0jdPw`
- 蟹かに城 — `DAHQmZ-GP3I`
- サイズ: **1080 × 1350 px / 4:5**

原則:

- フォント・レイアウト・ページ構成を維持
- 写真を主役にする
- 店名 / 写真 / 文章のみ差し替える
- コース順が分かる場合は最優先
- 未確認情報を捏造しない
- 強い表現を投稿内で重複させない

詳細は [rules/gourmet-canva.md](rules/gourmet-canva.md) を参照してください。

## Gmail入力

推奨件名:

```text
[グルメCanva] 店舗名
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

メモ：
・タンとハラミを推したい
```

写真を添付します。

## MD保存ルール

完成した投稿は原則:

```text
posts/YYYY/MM/YYYY-MM-DD_店舗名/post.md
```

に保存します。

制作結果、Canva URL、確認事項などは:

```text
posts/YYYY/MM/YYYY-MM-DD_店舗名/record.md
```

に保存します。

## 役割分担

- **Gmail** — 投入口
- **ChatGPT Automation** — 実行本体
- **Web検索** — 店舗調査 / 事実確認
- **Canva** — 完成デザイン
- **GitHub** — ルール / MD / 制作履歴の保管

