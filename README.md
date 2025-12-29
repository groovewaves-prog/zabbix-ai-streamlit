# Zabbix AI Assistant - Streamlit版

share.streamlit.io で動作するZabbix AIアシスタントのデモアプリです。

## 🎯 機能

| 優先度 | 機能 | コマンド例 |
|--------|------|-----------|
| 1位 | トポロジー自動設定 | 「トポロジーで監視設定して」 |
| 2位 | メンテナンスモード | 「WAN_ROUTER_01を30分メンテに」 |
| 3位 | メトリクス確認 | 「CORE_SW_01のメトリクス見せて」 |
| 4位 | アラート一覧 | 「現在のアラート教えて」 |
| 5位 | グラフ表示 | 「web-prod-01のCPU推移グラフで」 |
| 6位 | 動的コマンド＋キャッシュ | 新しいリクエストも学習 |

## 📁 ファイル構成

```
zabbix-ai-streamlit/
├── streamlit_app.py    # メインアプリ
├── requirements.txt    # 依存関係
├── data/
│   ├── topology.json   # トポロジーデータ
│   └── mock_data.json  # モックデータ
└── README.md
```

## 🚀 share.streamlit.io へのデプロイ

### 1. GitHubリポジトリを作成

```bash
# 新しいリポジトリを作成してプッシュ
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/zabbix-ai-streamlit.git
git push -u origin main
```

### 2. Streamlit Community Cloudでデプロイ

1. [share.streamlit.io](https://share.streamlit.io) にアクセス
2. 「New app」をクリック
3. リポジトリを選択
4. Main file path: `streamlit_app.py`
5. 「Deploy!」をクリック

### 3. (オプション) Google AI Studio APIキーの設定

実際のLLM連携をテストする場合：

1. Streamlit Cloudのアプリ設定を開く
2. 「Secrets」セクションに移動
3. 以下を追加：

```toml
GOOGLE_API_KEY = "your-api-key-here"
```

> ⚠️ APIキーがなくてもモック応答で全機能をデモできます

## 💻 ローカルでの実行

```bash
# 依存関係のインストール
pip install -r requirements.txt

# 実行
streamlit run streamlit_app.py

# ブラウザで http://localhost:8501 にアクセス
```

## 💬 使い方

### チャット入力

画面下部の入力欄にメッセージを入力して送信します。

```
👤「トポロジーで監視設定して」
🤖 ✅ Zabbix設定を生成しました：
   • ホスト: 11台
   • ホストグループ: 12個
   • トリガー: 15個
   • 依存関係: 10件
   [📋 生成された設定を表示]

👤「CPU80%超えてるサーバー教えて」
🤖 🔍 4台見つかりました：
   🔴 web-prod-01: 92.4%
   🔴 db-prod-01: 85.2%
   🟡 CORE_SW_01: 82.4%
   🟡 api-prod-01: 81.5%
```

### クイックアクション

サイドバーのボタンをクリックすると、よく使うコマンドを即座に実行できます。

### トポロジーアップロード

サイドバーからJSONファイルをアップロードして、独自のトポロジーを使用できます。

## 📊 トポロジーファイル形式

```json
{
  "デバイス名": {
    "layer": 1,
    "type": "ROUTER | FIREWALL | SWITCH | ACCESS_POINT",
    "parent_id": "親デバイス名 or null",
    "redundancy_group": "HAグループ名 or null",
    "metadata": {
      "vendor": "Cisco",
      "model": "ISR 4451-X",
      "location": "Floor 1"
    }
  }
}
```

## 🔄 コマンドキャッシュ

- 一度実行したコマンドは自動的にキャッシュ
- 同じ意図のリクエストは ⚡ Cached 表示で即応答
- サイドバーからキャッシュをクリア可能

## 🛠️ カスタマイズ

### モックデータの変更

`data/mock_data.json` を編集して、ホストやアラートを追加・変更できます。

### トポロジーの変更

`data/topology.json` を編集するか、サイドバーからアップロードします。

## 📝 制限事項

- share.streamlit.io ではファイルの永続化ができないため、アップロードしたトポロジーはセッション終了時にリセットされます
- 実際のZabbix APIとの連携はこのデモには含まれていません

## 🔜 本番環境への移行

このデモから本番環境への移行：

1. Zabbix APIクライアントの実装を追加
2. 認証・認可の実装
3. データの永続化（データベース連携）
4. MCP Server化してClaude等と連携

---

## ライセンス

社内検討用デモ
