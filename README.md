# タスク管理アプリの開発環境

FastAPI と HTML / CSS / JavaScript によるタスク管理アプリの初期環境を準備します。この段階の内容は、依存ライブラリ、接続設定のひな形、Git の除外設定、PR テンプレートです。API と画面は次の機能ブランチで実装します。

## 前提条件

- Python 3.10 以上
- Git、Docker、Docker Compose
- GitHub のリポジトリへ SSH でアクセスできること

以降は WSL / Linux / macOS のターミナルで実行します。Windows で Docker Desktop を利用する場合は、Ubuntu の WSL Integration を有効にし、`docker info` が成功することを確認してください。

## 1. 課題リポジトリを用意する

```bash
git clone git@github.com:Hayasaka-pape/2609-hayasaka-h-fastapi.git
cd 2609-hayasaka-h-fastapi
```

すでにクローンしている場合は、そのディレクトリに移動します。

## 2. 指定の MySQL-Sample を起動する

課題リポジトリと同じ親ディレクトリへ、指定の [MySQL-Sample](https://github.com/pygmalin-info/MySQL-Sample) をクローンします。

```bash
cd ..
git clone git@github.com:pygmalin-info/MySQL-Sample.git
cd MySQL-Sample
docker compose up -d
docker compose ps
docker compose logs mysql
```

すでにクローン済みの場合は、`MySQL-Sample` 内で起動コマンドを実行します。ログに `ready for connections` が表示されるまで待ちます。MySQL の Compose ファイルと設定は、この指定リポジトリのものを使用します。

| 項目 | 値 |
|---|---|
| ホスト | `localhost` |
| ポート | **`13306`** |
| データベース | `test_db` |
| ユーザー | `test_user` |
| パスワード | `test_password` |

接続を確認する場合は、次を順番に実行します。

```bash
docker compose exec mysql bash
mysql -u test_user -p test_db
```

求められたパスワードに `test_password` を入力します。MySQL に接続できたら `SELECT DATABASE();` を実行し、`test_db` が返ることを確認します。`exit` で MySQL を終了し、もう一度 `exit` でコンテナのシェルを終了します。

## 3. Python 仮想環境と依存ライブラリを準備する

```bash
cd ../2609-hayasaka-h-fastapi/fastapi_app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

`fastapi_app/.env` の内容を確認します。ホストから接続するポートは `13306` です。

```dotenv
DB_HOST=localhost
DB_PORT=13306
DB_NAME=test_db
DB_USER=test_user
DB_PASSWORD=test_password
DB_CHARSET=utf8mb4
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

`.env` と `.venv/` は Git に含めません。共有する設定のひな形は `.env.example` です。

依存ライブラリを読み込めることと、依存関係の整合性を確認します。

```bash
python -c "import fastapi, uvicorn, sqlalchemy, pymysql, pydantic_settings; print('dependencies: OK')"
python -m pip check
```

API 起動コマンドと画面の開き方は、アプリ実装を追加する PR でこの README に追記します。

## 4. 作業を終了する

仮想環境を終了し、指定リポジトリ内で MySQL を停止します。

```bash
deactivate
cd ../../MySQL-Sample
docker compose down
```

通常の `docker compose down` はコンテナを停止・削除し、データ用ボリュームを残します。データを維持するため `-v` は付けません。
