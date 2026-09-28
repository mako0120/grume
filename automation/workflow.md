# 自動制作フロー

```text
[1] Gmail
  件名: [グルメCanva] 店舗名
  写真添付
        │
        ▼
[2] ChatGPT Automation
  対象メールだけ取得
        │
        ▼
[3] 写真分析
  ・外観
  ・店内
  ・乾杯
  ・料理
  ・焼き工程
  ・アップ
  ・締め
        │
        ▼
[4] Web Research
  公式 > 公式SNS > Google / 食べログ
        │
        ▼
[5] 投稿設計
  コース順 + 写真順 + コピー
        │
        ▼
[6] Markdown
  post.md
        │
        ├──────────────┐
        ▼              ▼
[7] Canva           [8] GitHub
  テンプレコピー       post.md
  写真差替             record.md
  文章差替             INDEX更新
  保存
        │
        ▼
[9] Gmail返信
  Canva URL
  要確認事項
```

## 状態

- 未処理
- 処理中
- 要確認
- 完成
- 処理済み

同じ依頼は1回だけ処理する。
