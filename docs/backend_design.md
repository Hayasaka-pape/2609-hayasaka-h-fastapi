# タスク管理ツール バックエンド設計書

作成日: 2026-09-09
対象: FastAPI + SQLAlchemy 2.x + MySQL 8.0
API ベース URL: `http://localhost:8888`

## 1. この設計書の目的

この文書は、課題の API 仕様を「どのファイルに、どのデータ構造と処理を書くか」まで分解した実装前の設計書です。完成コードではありません。実装中に迷ったときは、次の順で確認します。

1. API の入出力名とステータスコード
2. DB に保存する列とリレーション
3. Pydantic、SQLAlchemy、ルーターの責務分担
4. 受け入れ条件に対応する確認方法

### 対象範囲

- タスクの作成・一覧・1件取得・更新・削除
- 完了状態とカテゴリによる一覧絞り込み
- カテゴリの一覧・作成
- 担当者の一覧・作成
- MySQL への永続化
- 別オリジンのフロントエンドからの CORS 通信

### 対象外

- ログインやユーザー認証
- カテゴリ・担当者の更新と削除
- タスクの複数カテゴリ、複数担当者
- 本番配備、権限管理、監査ログ

## 2. システム構成

```text
ブラウザ
HTML / CSS / JavaScript
http://localhost:3000
        │
        │ fetch（JSON）
        ▼
FastAPI
http://localhost:8888
        │
        │ SQLAlchemy 2.x + PyMySQL
        ▼
MySQL-Sample / MySQL 8.0
localhost:13306 / test_db
```

フロントエンドと FastAPI はポートが異なるため別オリジンです。FastAPI 側で、少なくとも `http://localhost:3000` と `http://127.0.0.1:3000` を明示的に許可します。

本設計は同期版 SQLAlchemy を使います。DB を操作するルート関数は基本的に `def` とし、同期 DB 処理を `async def` のイベントループ上で直接実行しない構成にします。

## 3. フォルダと責務

```text
backend/
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ config.py
│  ├─ database.py
│  ├─ dependencies.py
│  ├─ exceptions.py
│  ├─ models.py
│  ├─ schemas.py
│  ├─ crud/
│  │  ├─ __init__.py
│  │  ├─ tasks.py
│  │  ├─ categories.py
│  │  └─ assignees.py
│  └─ routers/
│     ├─ __init__.py
│     ├─ tasks.py
│     ├─ categories.py
│     └─ assignees.py
├─ tests/
├─ .env
├─ .env.example
└─ requirements.txt
```

| ファイル | 役割 | 書かないもの |
|---|---|---|
| `main.py` | FastAPI 生成、lifespan、CORS、router 登録 | 個別の CRUD 処理 |
| `config.py` | `.env` の読込と設定値 | DB セッション操作 |
| `database.py` | Engine、SessionLocal、Base | API の URL |
| `dependencies.py` | 1リクエスト1セッションの提供 | 個別テーブルの検索 |
| `models.py` | DB テーブル、外部キー、relationship | API 用入力チェック |
| `schemas.py` | リクエスト / レスポンスの型と検証 | commit や SQL |
| `crud/*.py` | SQLAlchemy による取得・保存・更新・削除 | HTTP URL とステータス |
| `routers/*.py` | URL、メソッド、status、依存関係、HTTP 例外 | テーブル定義 |
| `exceptions.py` | 任意の共通 404 / 409 ヘルパー | 必須ではない機能 |

小規模課題でも、API の入口と DB 処理を分けると、`/docs` の仕様を見ながら 1 機能ずつ実装しやすくなります。

## 4. 環境設定

`.env.example` を `.env` にコピーして使用します。

```dotenv
DB_HOST=localhost
DB_PORT=13306
DB_NAME=test_db
DB_USER=test_user
DB_PASSWORD=test_password
DB_CHARSET=utf8mb4
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

SQLAlchemy の接続 URL は次の意味になります。

```text
mysql+pymysql://test_user:********@localhost:13306/test_db?charset=utf8mb4
│     │          │                    │       │     │
│     │          │                    │       │     └─ DB 名
│     │          │                    │       └─ Docker が公開するポート
│     │          │                    └─ FastAPI がホストで動くため localhost
│     │          └─ 認証情報（ログへそのまま出さない）
│     └─ Python の MySQL ドライバー
└─ DB 方言
```

文字列連結でも動きますが、パスワード中の特殊文字を安全に扱えるよう `sqlalchemy.URL.create()` で組み立てる設計を推奨します。

Engine の方針:

- `pool_pre_ping=True`: プール内の切断済み接続を利用前に確認する。
- `pool_recycle=3600`: MySQL 側の接続タイムアウト対策。
- `echo=False`: 通常は SQL と値を大量に出力しない。学習時だけ一時的に `True`。

Session の方針:

- `autocommit=False`
- `autoflush=False`
- `expire_on_commit=False`
- 1 HTTP リクエストにつき 1 Session
- `yield` の後に必ず `close()`

## 5. データベース設計

### 5.1 ER 図

```mermaid
erDiagram
    CATEGORIES ||--o{ TASKS : "分類する"
    ASSIGNEES ||--o{ TASKS : "担当する"

    CATEGORIES {
        int id PK
        varchar name UK
    }

    ASSIGNEES {
        int id PK
        varchar name UK
    }

    TASKS {
        int id PK
        varchar title
        text description NULL
        boolean is_done
        int category_id FK NULL
        int assignee_id FK NULL
        datetime created_at
        datetime updated_at
    }
```

関係はどちらも多対一です。

- 1つの Task が参照できる Category は 0 または 1件。
- 1つの Category は複数 Task から参照できる。
- 1つの Task が参照できる Assignee は 0 または 1人。
- 1人の Assignee は複数 Task から参照できる。

### 5.2 `categories`

| カラム | MySQL 型 | NULL | 制約 | 用途 |
|---|---|---:|---|---|
| `id` | `INT` | 不可 | PK, AUTO_INCREMENT | API の `id` |
| `name` | `VARCHAR(100)` | 不可 | UNIQUE | API の `name` |

同名カテゴリを複数作る必要がない課題なので `UNIQUE` を付けます。前後空白を除去し、空白だけの値は Pydantic で拒否します。

### 5.3 `assignees`

| カラム | MySQL 型 | NULL | 制約 | 用途 |
|---|---|---:|---|---|
| `id` | `INT` | 不可 | PK, AUTO_INCREMENT | API の `id` |
| `name` | `VARCHAR(100)` | 不可 | UNIQUE | API の `name` |

この1人用学習アプリでは同名を禁止します。実務で同姓同名を扱う場合は、名前ではなく社員番号などを一意にします。

### 5.4 `tasks`

| カラム | MySQL 型 | NULL | 制約 / 初期値 | API との対応 |
|---|---|---:|---|---|
| `id` | `INT` | 不可 | PK, AUTO_INCREMENT | `id` |
| `title` | `VARCHAR(255)` | 不可 | 1～255文字 | `title` |
| `description` | `TEXT` | 可 | 初期値 `NULL` | `description` |
| `is_done` | `BOOLEAN` | 不可 | 初期値 `FALSE` | `is_done` |
| `category_id` | `INT` | 可 | FK, index | リクエストの `category_id` |
| `assignee_id` | `INT` | 可 | FK, index | リクエストの `assignee_id` |
| `created_at` | `DATETIME` | 不可 | 作成時に設定 | `created_at` |
| `updated_at` | `DATETIME` | 不可 | 作成・更新時に設定 | `updated_at` |

MySQL の `BOOLEAN` は実体として `TINYINT(1)` ですが、Python / JSON では `bool` / `true` / `false` として扱います。

外部キー:

```text
tasks.category_id -> categories.id
tasks.assignee_id -> assignees.id
```

両方を `nullable=True` にします。将来カテゴリや担当者の削除 API を追加してもタスクを残せるよう、外部キーの `ondelete="SET NULL"` を推奨します。

推奨インデックス:

- `tasks.is_done`: 完了状態の絞り込み用
- `tasks.category_id`: カテゴリ絞り込みと結合用
- `tasks.assignee_id`: 結合用

日時は API 例と同じ、タイムゾーン表記を持たない ISO 形式へ変換しやすい `DATETIME` を使用します。MySQL-Sample の `TZ` は `Asia/Tokyo` です。`server_default=func.now()` と `onupdate=func.now()` を利用し、DB とアプリで時刻方針を混在させません。

### 5.5 ORM リレーション

`Task` 側に次を定義します。

- `Task.category`: `Category | None`
- `Task.assignee`: `Assignee | None`

逆方向は次のとおりです。

- `Category.tasks`: `list[Task]`
- `Assignee.tasks`: `list[Task]`

Task を削除しても Category / Assignee は削除しません。親からタスクを連鎖削除する要件もないため、誤って `delete` cascade を付けないようにします。

一覧・1件取得では、`selectinload(Task.category)` と `selectinload(Task.assignee)` などで関連データを読み込みます。レスポンスを作るときに Task ごとの追加 SQL が発生する N+1 問題を避けられます。

## 6. Pydantic スキーマ設計

リクエスト用スキーマとレスポンス用スキーマを分けます。DB の `category_id` を入力で受けても、出力では `category` オブジェクトを返すためです。

レスポンス用モデルには Pydantic v2 の次の設定を付けます。

```python
model_config = ConfigDict(from_attributes=True)
```

これにより、辞書だけでなく SQLAlchemy オブジェクトの属性からレスポンスを構成できます。

### 6.1 Category / Assignee

```text
CategoryCreate                 CategoryResponse
└─ name: str (1..100)          ├─ id: int
                               └─ name: str

AssigneeCreate                 AssigneeResponse
└─ name: str (1..100)          ├─ id: int
                               └─ name: str
```

`name` は前後空白を除去した後で空にならないことを検証します。

### 6.2 TaskCreate

| フィールド | 型 | 必須 | 初期値 / 検証 |
|---|---|---:|---|
| `title` | `str` | はい | 前後空白除去後 1～255文字 |
| `description` | `str \| None` | いいえ | `None`、必要なら最大 2000文字 |
| `category_id` | `int \| None` | いいえ | `None` または正の整数 |
| `assignee_id` | `int \| None` | いいえ | `None` または正の整数 |

POST 仕様に `is_done` はないため、作成時はバックエンドが `False` にします。

### 6.3 TaskUpdate

PUT は全置換として扱い、5項目を受け取ります。

| フィールド | 型 | 必須 | 補足 |
|---|---|---:|---|
| `title` | `str` | はい | 空白だけは禁止 |
| `description` | `str \| None` | はい | JSON の `null` で説明を解除 |
| `is_done` | `bool` | はい | 完了 / 未完了 |
| `category_id` | `int \| None` | はい | `null` でカテゴリ解除 |
| `assignee_id` | `int \| None` | はい | `null` で担当者解除 |

チェックボックスだけを変更するときも、フロントエンドは現在値からこの5項目を組み立てます。

### 6.4 TaskResponse

```text
TaskResponse
├─ id: int
├─ title: str
├─ description: str | None
├─ is_done: bool
├─ category: CategoryResponse | None
├─ assignee: AssigneeResponse | None
├─ created_at: datetime
└─ updated_at: datetime
```

出力例:

```json
{
  "id": 1,
  "title": "資料をまとめる",
  "description": "月曜の会議用スライド",
  "is_done": false,
  "category": { "id": 2, "name": "仕事" },
  "assignee": { "id": 1, "name": "山田" },
  "created_at": "2026-07-28T10:00:00",
  "updated_at": "2026-07-28T10:00:00"
}
```

## 7. API 設計

### 7.1 一覧

| Method | Path | 正常時 | Request | Response |
|---|---|---:|---|---|
| GET | `/tasks` | 200 | query 任意 | `TaskResponse[]` |
| POST | `/tasks` | 201 | `TaskCreate` | `TaskResponse` |
| GET | `/tasks/{task_id}` | 200 | path | `TaskResponse` |
| PUT | `/tasks/{task_id}` | 200 | `TaskUpdate` | `TaskResponse` |
| DELETE | `/tasks/{task_id}` | 204 | path | 本文なし |
| GET | `/categories` | 200 | なし | `CategoryResponse[]` |
| POST | `/categories` | 201 | `CategoryCreate` | `CategoryResponse` |
| GET | `/assignees` | 200 | なし | `AssigneeResponse[]` |
| POST | `/assignees` | 201 | `AssigneeCreate` | `AssigneeResponse` |

### 7.2 GET `/tasks`

任意クエリ:

- `is_done: bool | None`
- `category_id: int | None`

条件は指定されたものだけ加え、2つある場合は AND にします。

```text
GET /tasks?is_done=false&category_id=2
```

重要な分岐:

```python
if is_done is not None:
    # false も条件として追加する
```

`if is_done:` とすると `false` のとき条件が消えるため不正です。

一覧の方針:

- 該当なしは 404 ではなく `[]`。
- 存在しない `category_id` を絞り込みに指定しても `[]`。
- 表示順を安定させるため `created_at DESC, id DESC`。
- Category / Assignee を eager load する。

### 7.3 POST `/tasks`

処理順:

1. Pydantic が形式・必須・長さを検証する。
2. `category_id` があれば Category の存在を確認する。
3. `assignee_id` があれば Assignee の存在を確認する。
4. `is_done=False` で Task を作る。
5. `session.add()` と `commit()`。
6. 関連を含めて再取得する。
7. 201 で `TaskResponse` を返す。

関連 ID が存在しない場合は本設計では 404 とし、Task は登録しません。

### 7.4 GET `/tasks/{task_id}`

- Task、Category、Assignee をまとめて取得する。
- 存在すれば 200。
- 存在しなければ `404 {"detail": "Task not found"}`。

### 7.5 PUT `/tasks/{task_id}`

処理順:

1. 更新対象 Task の存在確認。
2. 指定された Category / Assignee の存在確認。
3. `title`, `description`, `is_done`, `category_id`, `assignee_id` を更新。
4. `commit()`。
5. 関連を含む最新状態を再取得。
6. 200 で返す。

`category_id: null` / `assignee_id: null` は関連解除です。

### 7.6 DELETE `/tasks/{task_id}`

- 存在しなければ 404。
- `session.delete()` と `commit()`。
- 成功時は 204 で、JSON の `null` も返さない。

ルーターのレスポンスクラスまたは空の `Response(status_code=204)` を利用し、本文が本当に空であることを確認します。

### 7.7 Categories / Assignees

GET は `id ASC` で返します。

POST の処理:

1. Pydantic で空白除去と長さを検証。
2. 同名がないか確認。
3. `add()`、`commit()`、`refresh()`。
4. 201 で返す。

重複時は DB の UNIQUE 制約を最終防衛線とし、`IntegrityError` を捕捉して rollback 後に 409 を返します。

## 8. HTTP エラー方針

| Status | 条件 | `detail` の例 |
|---:|---|---|
| 404 | Task が存在しない | `Task not found` |
| 404 | 指定 Category が存在しない | `Category not found` |
| 404 | 指定 Assignee が存在しない | `Assignee not found` |
| 409 | Category 名が重複 | `Category name already exists` |
| 409 | Assignee 名が重複 | `Assignee name already exists` |
| 422 | 空タイトル、不正な型、0以下の ID | FastAPI 標準の検証詳細 |
| 500 | 想定外の DB 障害 | 内部情報を含まない一般メッセージ |

クライアントへ DB の接続文字列、SQL、スタックトレースを返しません。詳細はサーバーログ、利用者向けには安全な `detail` を使います。

## 9. トランザクション方針

GET は commit しません。POST / PUT / DELETE は、1リクエストの変更を1トランザクションにします。

```text
成功: DB操作 -> commit -> refresh / 再検索 -> レスポンス
失敗: DB操作 -> 例外 -> rollback -> HTTPエラー
```

特に次を忘れず rollback します。

- `IntegrityError`
- `SQLAlchemyError`
- `commit()` 中の例外

Category / Assignee の存在確認は Task を追加・変更する前に行います。外部キー違反をクライアントへそのまま露出させません。

## 10. CORS 設計

許可オリジン:

```text
http://localhost:3000
http://127.0.0.1:3000
```

設定:

```text
allow_origins     = 上記の配列
allow_credentials = False
allow_methods     = ["*"]
allow_headers     = ["*"]
```

この課題は Cookie 認証がないため `allow_credentials=False` で十分です。`localhost` と `127.0.0.1` は同じ PC を指しても、ブラウザでは別オリジンです。

POST / PUT / DELETE や JSON の送信では、ブラウザが事前に OPTIONS リクエストを送る場合があります。CORS ミドルウェアがこれへ応答できることも受け入れ確認に含めます。

## 11. 起動時のテーブル作成

課題要件に合わせ、FastAPI の lifespan 内で次を行います。

```text
Base.metadata.create_all(bind=engine)
```

実装上の注意:

- `models` を読み込んだ後に呼ぶ。
- 存在しないテーブルを作る処理であり、既存列の変更はしない。
- 学習課題では十分だが、実務のスキーマ変更には Alembic などの migration を使う。
- MySQL が準備完了前なら起動に失敗するため、Docker のログを確認する。

## 12. 1リクエストの処理フロー

```text
ブラウザ操作
  -> fetch が JSON / query を作る
  -> CORS ミドルウェア
  -> router が path・body・query を受ける
  -> Pydantic が検証
  -> Depends(get_db) が Session を渡す
  -> CRUD が SQLAlchemy で DB を操作
  -> commit / rollback
  -> response_model が ORM を JSON へ変換
  -> ブラウザが state を更新
  -> JavaScript が必要な DOM だけ再描画
```

境界ごとの名前変換:

```text
HTML select.value        "2"      （文字列）
JavaScript request       2         （数値 category_id）
DB tasks.category_id     2         （外部キー）
API response.category    {id, name}（入れ子）
画面表示                 "仕事"   （category.name）
```

## 13. フロントエンドとの API 対応

| 画面操作 | 呼ぶ API | 成功後の画面処理 |
|---|---|---|
| 初期表示 | `GET /tasks`, `/categories`, `/assignees` | 選択肢と一覧を描画 |
| タスク追加 | `POST /tasks` | 入力をリセットし一覧再取得 |
| 完了切替 | `PUT /tasks/{id}` | 現在の5項目を送り一覧再取得 |
| 編集を開く | `GET /tasks/{id}` | 最新値を編集フォームへ設定 |
| 編集保存 | `PUT /tasks/{id}` | 閉じて一覧再取得 |
| 削除 | `DELETE /tasks/{id}` | 204 後に一覧再取得 |
| 状態絞り込み | `GET /tasks?is_done=...` | 返った一覧だけ描画 |
| カテゴリ絞り込み | `GET /tasks?category_id=...` | 返った一覧だけ描画 |
| カテゴリ追加 | `POST /categories` | 3つのカテゴリ選択欄を更新 |
| 担当者追加 | `POST /assignees` | 2つの担当者選択欄を更新 |

更新時はレスポンスの入れ子を ID へ戻します。

```javascript
{
  title: task.title,
  description: task.description,
  is_done: true,
  category_id: task.category?.id ?? null,
  assignee_id: task.assignee?.id ?? null
}
```

## 14. 実装順序

### Phase 1: DB 接続

- `.env` を読み込む。
- Engine / Session / Base を作る。
- MySQL へ接続できることを確認する。

### Phase 2: モデルとテーブル

- Category / Assignee / Task を定義する。
- lifespan から `create_all()` する。
- DB クライアントで3テーブル、PK、FK、NULL、index を確認する。

### Phase 3: 参照データ API

- schemas を作る。
- Category GET / POST を実装する。
- Assignee GET / POST を実装する。
- `/docs` で登録と一覧を確認する。

### Phase 4: Task API

- Task の schemas を作る。
- 1件取得、一覧、POST、PUT、DELETE の順に実装する。
- 関連の入れ子と status code を確認する。

### Phase 5: フィルターと CORS

- `is_done` と `category_id` の条件を追加する。
- 複合条件を確認する。
- CORS を設定し、ブラウザから接続する。

### Phase 6: 再起動と記録

- FastAPI を止めて再起動する。
- データが MySQL に残ることを確認する。
- 一連の UI 操作を撮影する。

## 15. 受け入れ条件対応表

| 受け入れ条件 | 設計 / 確認ポイント |
|---|---|
| 起動時にテーブル作成 | lifespan の `Base.metadata.create_all()` |
| MySQL へ永続化 | `localhost:13306/test_db` へ接続して commit |
| 再起動後も残る | FastAPI 再起動後に GET、Docker named volume |
| 多対一の関連 | Task の2つの FK と relationship |
| 関連を未設定にできる | FK を nullable、API は `null` 許容 |
| Category / Assignee 登録 | 各 GET / POST と 201 |
| Task CRUD | 5エンドポイント |
| 完了切替 | `is_done` を PUT して DB 保存 |
| 絞り込み | 任意 query と AND 条件 |
| 入れ子レスポンス | `TaskResponse.category` / `assignee` |
| 指定 status code | POST 201、DELETE 204、未存在 404 |
| `/docs` で操作 | Pydantic と response_model |
| CORS エラーなし | 2つの frontend origin を許可 |
| 日本語を保存 | MySQL / 接続を `utf8mb4` |

## 16. 手動テストシナリオ

1. MySQL-Sample を起動する。
2. FastAPI を起動し、3テーブルが作られたことを確認する。
3. `POST /categories` で「仕事」を作る。201 と `{id, name}` を確認する。
4. `POST /assignees` で「山田」を作る。201 を確認する。
5. それぞれの GET で登録内容を確認する。
6. `POST /tasks` で両方を設定したタスクを作る。
7. レスポンスが `category` / `assignee` の入れ子であることを確認する。
8. `GET /tasks?is_done=false` に表示されることを確認する。
9. PUT で `is_done=true` にする。
10. `GET /tasks?is_done=true` に表示されることを確認する。
11. PUT で説明を変更し、Category / Assignee を `null` にして解除する。
12. 存在しない Task の GET / PUT / DELETE が 404 になることを確認する。
13. DELETE の 204 に本文がないことを確認する。
14. FastAPI を再起動し、削除していないデータが残ることを確認する。
15. `http://localhost:3000` から同じ操作を行い、CORS エラーがないことを確認する。

## 17. よくある失敗と確認先

| 症状 | 主な原因 | 最初の確認 |
|---|---|---|
| DB 接続拒否 | ポートを 3306 にしている / 初期化中 | `.env` の 13306、Docker logs |
| テーブルがない | models を import 前に create_all | lifespan と import 順 |
| `is_done=false` が効かない | `if is_done:` と書いた | `is not None` |
| category が JSON にならない | relationship / from_attributes 不足 | model と response schema |
| 更新で値が消える | PUT に全項目を送っていない | Network の Request Payload |
| DELETE で JSON エラー | 204 を `response.json()` した | frontend `request()` |
| ブラウザだけ失敗 | CORS origin 不一致 | localhost / 127.0.0.1 / port |
| 日本語が文字化け | charset の不一致 | `utf8mb4` |
| 同名追加後に 500 | UNIQUE 例外未処理 | `IntegrityError` と rollback |
| Docker 再作成でデータ消失 | `down -v` を実行 | named volume の扱い |

## 18. 参考資料

- [MySQL-Sample 公式リポジトリ](https://github.com/pygmalin-info/MySQL-Sample)
- [MySQL-Sample compose.yaml](https://github.com/pygmalin-info/MySQL-Sample/blob/main/compose.yaml)
- [FastAPI - Request Body](https://fastapi.tiangolo.com/tutorial/body/)
- [FastAPI - Response Status Code](https://fastapi.tiangolo.com/tutorial/response-status-code/)
- [FastAPI - CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [FastAPI - Dependencies with yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
- [SQLAlchemy 2.0 - ORM Quick Start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [SQLAlchemy 2.0 - Engine Configuration](https://docs.sqlalchemy.org/en/20/core/engines.html)
- [Pydantic - Models from attributes](https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances)
- [Pydantic Settings - dotenv](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#dotenv-env-support)
