"""FastAPIアプリ全体の設定と、各機能の組み立てを担当する場所。

- 起動時に、存在しないテーブルを作成する。
- フロントエンドとの通信に必要なCORSを設定する。
- タスク・カテゴリー・担当者のAPIを登録する。
"""

# yieldの前後で、アプリの起動処理と終了処理を分けるために使用する。
from contextlib import asynccontextmanager
import logging

# FastAPIアプリを作成するためのクラスを読み込む。
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

# 異なるオリジンから、ブラウザがAPIのレスポンスを読み取れるようにする。
from fastapi.middleware.cors import CORSMiddleware

# .envなどから読み込んだ設定を取得する関数を読み込む。
from .DataAccessLayer.database import get_settings

# Base：モデルが共有するテーブル定義を保持する。
# engine：データベースへの接続を管理する。
from .DataAccessLayer.database import Base, engine

# モデルのクラス定義を実行し、各テーブルをBase.metadataへ登録する。
# _modelsは、このファイル内で直接使わず、読み込み自体が目的であることを示す別名。
from .Model import models as _models

# タスク・カテゴリー・担当者のAPIを定義したモジュールを読み込む。
from .Controller import assignees, categories, tasks


# アプリ起動時の準備と、終了時の処理をまとめて管理する。
@asynccontextmanager  # 非同期ジェネレーターを、開始・終了処理を管理する仕組みに変換する。
async def lifespan(app: FastAPI):
    # yieldより前は、アプリがリクエストを受け付ける前に実行される。
    # metadataには、読み込み済みのモデルのテーブル定義が入っている。
    Base.metadata.create_all(
        bind=engine
    )  # 指定した接続先に、存在しないテーブルを作る。

    # create_all()は、既存テーブルの列追加や型変更までは行わない。
    # 接続先のデータベース自体は、あらかじめ作成しておく必要がある。

    # ここで処理を一時停止し、FastAPIへ制御を渡してアプリを稼働させる。
    try:
        yield
    finally:
        # 終了時には接続プールも閉じる。
        engine.dispose()


# 設定オブジェクトを取得し、アプリ全体の設定に利用する。
settings = get_settings()


# FastAPIアプリ本体を作成する。
app = FastAPI(
    title="Task Manager API",  # Swagger UIなどに表示するAPI名を指定する。
    lifespan=lifespan,  # 関数自体を渡し、起動・終了時の実行をFastAPIに任せる。
)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    # SQLや接続情報はレスポンスに含めず、詳細はサーバーログへ記録する。
    logging.getLogger(__name__).error(
        "Database operation failed: %s %s", request.method, request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Database operation failed"},
    )


# リクエスト・レスポンスの処理に、CORS用のミドルウェアを追加する。
# オリジンは「通信方式・ホスト名・ポート番号」の組み合わせを指す。
# 例：http://localhost:3000とhttp://localhost:8000は異なるオリジンである。
app.add_middleware(
    CORSMiddleware,
    # 設定から、許可するフロントエンドのオリジン一覧を取得する。
    allow_origins=settings.allowed_origins,
    # Cookieなどの資格情報付きクロスオリジン通信を許可する設定は有効にしない。
    allow_credentials=False,
    # CORS上、すべてのHTTPメソッドを許可する。
    # 未実装のエンドポイントが、この指定だけで使えるようになるわけではない。
    allow_methods=["*"],  # "*"はすべてを表す。
    # CORS上、リクエストで使用するすべてのヘッダーを許可する。
    allow_headers=["*"],
)

# CORSはブラウザ向けの仕組みであり、認証やAPIのアクセス制限の代わりではない。


# 各Controllerのルーターを登録し、アプリから利用できるようにする。
# URLのprefixや個々の処理は、それぞれのController側で定義する。
app.include_router(tasks.router)  # /tasksに関するAPIを登録する。
app.include_router(categories.router)  # /categoriesに関するAPIを登録する。
app.include_router(assignees.router)  # /assigneesに関するAPIを登録する。
