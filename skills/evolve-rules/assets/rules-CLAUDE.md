# Domain-Specific Rules

このディレクトリには製品・領域別のルールを配置する。
CLAUDE.md の肥大化を防ぎ、関連作業時のみ参照される。

## 構造

```
.claude/rules/
├── <domain>/
│   ├── general.md      ← 汎用ルール
│   └── <specific>.md   ← 特定トピックのルール
└── ...
```

## 命名規則

- ディレクトリ名: 製品名・領域名（小文字、ハイフン区切り）
- ファイル名: `general.md` または具体的なトピック名

## ルールの参照タイミング

- 関連する作業を開始する前に、該当ドメインのルールを確認する
- 例: PowerShell スクリプトを書く前に `microsoft/` を確認
- 例: Docker 操作の前に `docker/` を確認
