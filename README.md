# タスク管理アプリ（FastAPI / MySQL）

タスクの追加・一覧・完了切替・編集・削除をブラウザから行うアプリです。カテゴリと担当者を登録してタスクに関連付け、完了状態とカテゴリで絞り込めます。データは指定の [MySQL-Sample](https://github.com/pygmalin-info/MySQL-Sample) が起動する MySQL に保存します。

## 必要なもの

- Python 3.10 以上
- Git、Docker、Docker Compose（`docker compose` コマンド）
- ブラウザ
- GitHub を SSH で利用できる環境

Windows では WSL の Ubuntu ターミナルで、MySQL と Python の操作をそろえて行う手順を推奨します。Docker Desktop を利用する場合は Ubuntu の WSL Integration を有効にし、`docker info` が成功することを確認してください。以降のコマンドは WSL / Linux / macOS 用です。PowerShell での仮想環境作成方法も後述します。

## フォルダ構成

```text
2609-hayasaka-h-fastapi/
├── fastapi_app/
│   ├── task_app/
│   │   ├── main.py                 # アプリ起動・テーブル作成・CORS
│   │   ├── dependencies.py         # リクエスト単位のDBセッション
│   │   ├── Controller/             # APIルートとHTTPエラー
│   │   ├── Model/                  # ORMモデルと入出力スキーマ
│   │   ├── DataAccessLayer/        # DB接続・設定・検索・保存
│   │   └── Views/                  # HTML / CSS / JavaScript
│   ├── tests/                     # APIの自動テスト
│   ├── .env.example               # ローカル接続設定のひな形
│   └── requirements.txt
├── screenshots/                   # 画面操作と永続化の確認記録
├── docs/                          # 設計・学習資料
├── .github/pull_request_template.md
├── .gitignore
└── README.md
```

`docs/` は実装前の設計・学習資料を含みます。セットアップにはこの README の現行のフォルダ名と起動コマンドを使用してください。MySQL の Compose ファイルや設定ファイルは課題ソースに同梱しません。

## 1. ソースコードを用意する

親ディレクトリでリポジトリをクローンします。すでにクローンしている場合は不要です。

```bash
git clone git@github.com:Hayasaka-pape/2609-hayasaka-h-fastapi.git
cd 2609-hayasaka-h-fastapi
```

レビュー中のコードを確認する場合は、提出 PR のブランチをチェックアウトしてください。ZIP から実行する場合は展開したフォルダが以降の「課題リポジトリ直下」です。

## 2. 指定の MySQL-Sample を起動する

課題リポジトリと同じ親ディレクトリにクローンします。自作の MySQL 設定ファイルは不要です。

```bash
cd ..
git clone git@github.com:pygmalin-info/MySQL-Sample.git
cd MySQL-Sample
docker compose up -d
docker compose ps
docker compose logs mysql
```

すでに `MySQL-Sample` をクローンしている場合はそのフォルダ内で `docker compose up -d` を実行してください。ログに `ready for connections` と表示されるまで初期化を待ちます。

| 項目 | 値 |
|---|---|
| ホスト | `localhost` |
| ポート | **`13306`**（ホスト側） |
| データベース | `test_db` |
| ユーザー | `test_user` |
| パスワード | `test_password` |

SQL で確認したい場合は次の順に実行し、パスワード入力で `test_password` を入力します。

```bash
docker compose exec mysql bash
mysql -u test_user -p test_db
```

MySQL 内では `SHOW TABLES;`、終了時は `exit` を実行します。コンテナ内のシェルも `exit` で終了します。テーブルは次の FastAPI 初回起動時に作成されます。

## 3. バックエンドの準備

`MySQL-Sample` から課題リポジトリの `fastapi_app` に移動します。

```bash
cd ../2609-hayasaka-h-fastapi/fastapi_app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

`fastapi_app/.env` に次の値を設定します。MySQL に接続するポートは通常の `3306` ではなく **`13306`** です。

```dotenv
DB_HOST=localhost
DB_PORT=13306
DB_NAME=test_db
DB_USER=test_user
DB_PASSWORD=test_password
DB_CHARSET=utf8mb4
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

`.env` は `.gitignore` の対象です。共有するのは `.env.example` です。

PowerShell を使用する場合は、課題リポジトリ直下から次を実行します。

```powershell
cd fastapi_app
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## 4. バックエンドを起動する

仮想環境を有効にした `fastapi_app` ディレクトリで実行します。

```bash
python -m uvicorn task_app.main:app --reload --host 127.0.0.1 --port 8888
```

- Swagger UI: [http://localhost:8888/docs](http://localhost:8888/docs)
- API ベース URL: `http://localhost:8888`

初回起動時に `test_db` に `categories`、`assignees`、`tasks` テーブルを作成します。既存のテーブルとデータはそのまま使用します。テーブル定義の変更を既存 DB に反映するマイグレーション機能はありません。

## 5. フロントエンドを開く

別のターミナルを開き、課題リポジトリ直下で実行します。

```bash
python3 -m http.server 3000 --bind 127.0.0.1 --directory fastapi_app/task_app/Views
```

PowerShell では `python3` を `py` に置き換えます。ブラウザで [http://localhost:3000](http://localhost:3000) を開きます。HTML ファイルをダブルクリックせず、HTTP サーバー経由で開いてください。

API 接続先は `fastapi_app/task_app/Views/js/api.js` の `API_BASE_URL` に設定しています。ポートを変更する場合は API 接続先、起動コマンド、`.env` の `CORS_ORIGINS` を合わせて変更し、FastAPI を再起動します。

## 6. 操作と動作確認

1. 画面でカテゴリと担当者をそれぞれ登録する（Swagger UI の `POST /categories`、`POST /assignees` からも登録可能）。
2. タイトル・説明・カテゴリ・担当者を入力してタスクを追加し、一覧への反映を確認する。
3. 完了チェックを切り替え、未完了 / 完了とカテゴリの絞り込みを確認する。
4. 編集画面でタイトルや説明、カテゴリ、担当者を変更して保存する。カテゴリと担当者を未設定に戻すこともできる。
5. FastAPI を `Ctrl+C` で停止して同じ起動コマンドで再起動し、ブラウザを再読み込みして登録内容が残ることを確認する。
6. MySQL-Sample でも `docker compose down` → `docker compose up -d` を実行し、MySQL の起動を待って再読み込みする。データを確認した後、タスクを削除して一覧から消えることを確認する。

提出用のスクリーンショットと実施内容は [screenshots/README.md](screenshots/README.md) にまとめています。

### 自動テスト

仮想環境を有効にした `fastapi_app` で実行します。

```bash
python -m pytest -q
```

テストは FastAPI の実ルーター・スキーマ・データアクセス層を使い、接続先だけをテストごとに独立した一時 SQLite DB に置き換えます。`test_db` を変更しません。CRUD、関連の変更・解除、絞り込み、入力エラー、404 / 409、CORS、DB エラー時の応答を確認します。MySQL 固有の動作と再起動後の永続化は上記の実環境確認で扱います。詳細は [fastapi_app/tests/README.md](fastapi_app/tests/README.md) を参照してください。

## API 一覧

| メソッド | パス | 内容 | 成功時 |
|---|---|---|---|
| GET | `/tasks` | 一覧。`is_done` / `category_id` で絞り込み | 200 |
| POST | `/tasks` | タスク追加 | 201 |
| GET | `/tasks/{task_id}` | 1 件取得 | 200 |
| PUT | `/tasks/{task_id}` | タスク全項目更新・完了切替 | 200 |
| DELETE | `/tasks/{task_id}` | タスク削除 | 204（本文なし） |
| GET / POST | `/categories` | カテゴリ一覧 / 作成 | 200 / 201 |
| GET / POST | `/assignees` | 担当者一覧 / 作成 | 200 / 201 |

タスクの POST では `title` が必須です。`description`、`category_id`、`assignee_id` は省略または `null` にできます。作成時は未完了です。PUT は `title`、`description`、`is_done`、`category_id`、`assignee_id` の 5 項目をすべて送ります。関連 ID を `null` にすると関連を解除します。

タイトルは空白除去後 1〜255 文字、カテゴリ・担当者名は 1〜100 文字です。空白だけの入力や不正な型・ID は 422、存在しないタスク・参照先は 404、名前の重複は 409 になります。カテゴリ・担当者の編集・削除およびログインは課題の対象外です。

## 7. 作業を終了する

フロントエンドと FastAPI のターミナルで、それぞれ `Ctrl+C` を押します。続いて MySQL-Sample ディレクトリで次を実行します。

```bash
docker compose down
```

通常の `down` はコンテナを停止・削除し、データ用ボリュームを残します。登録データを残すため、`docker compose down -v` は実行しないでください。

## 開発・提出のブランチフロー

提出先は指定に従い `Hayasaka-pape/2609-hayasaka-h-fastapi` です。課題の Issue を GitHub Projects で作成し、タイトルに付けた番号と `feature/#番号` の番号をそろえます。

```bash
git switch develop
git pull origin develop
git switch -c 'feature/#番号'
# 実装と動作確認後、対象ファイルを指定して add / commit / push
git add <対象ファイル>
git commit -m "fix:変更内容を記載"
git push --set-upstream origin 'feature/#番号'
```

`feature/#番号` から `develop` へ PR を作成し、レビューの approve 後にマージします。課題提出時に `develop` から `main` へ PR を作成します。環境構築のみの初回 PR を除き、承認前に自己マージしません。PR には変更内容・確認手順・確認結果・スクリーンショットを記載します。

## 接続できない場合

| 症状 | 確認すること |
|---|---|
| MySQL 接続拒否 | `docker compose ps` と `docker compose logs mysql`、`.env` の `localhost:13306` |
| `.env` の設定エラー | `fastapi_app/.env` を作成したか |
| `ModuleNotFoundError` | 仮想環境を有効化したか、`requirements.txt` をインストールしたか、`fastapi_app` で起動したか |
| ブラウザから接続できない | API が 8888、フロントが 3000 で動作しているか。オリジンが `.env` の許可一覧と一致するか |
| 8888 / 3000 / 13306 が使用中 | 同じアプリを二重起動していないか。自分が起動した不要なプロセス・コンテナを停止する |
