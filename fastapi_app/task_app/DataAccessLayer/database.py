"""データベース接続と環境設定を管理する場所。

- .envファイルからデータベース設定とCORS設定を読み込む。
- MySQLへ接続するためのEngineを作成する。
- データベース操作に使用するSessionLocalを作成する。
- 各モデルの基底クラスとなるBaseを定義する。
"""

# 一度作成した設定オブジェクトをキャッシュするために使用する。
from functools import lru_cache

# OSに依存しない方法でファイルパスを操作するために使用する。
from pathlib import Path

# SQLAlchemyの接続URLとEngineを作成する機能を読み込む。
from sqlalchemy import URL, create_engine

# モデルの基底クラスとセッション作成機能を読み込む。
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# .envファイルから設定値を読み込む機能を読み込む。
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# .envファイルから読み込む設定項目を定義する。
class Settings(BaseSettings):

    # データベースの接続情報を受け取る。
    db_host: str
    db_port: int = Field(gt=0, le=65535)
    db_name: str
    db_user: str
    db_password: str

    # 文字コードが未指定の場合はutf8mb4を使用する。
    db_charset: str = "utf8mb4"

    # 接続を許可するフロントエンドのURLを受け取る。
    cors_origins: str

    # BaseSettingsが設定値を読み込む方法を指定する。
    model_config = SettingsConfigDict(
        # このファイルから3階層上にある.envファイルを指定する。
        # __file__：現在実行しているファイルのパスを表す。
        # resolve()：絶対パスに変換する。
        # parents[2]：3階層上の親ディレクトリを取得する。
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        # .envファイルをUTF-8として読み込む。
        env_file_encoding="utf-8",
        # Settingsクラスに定義していない環境変数は無視する。
        extra="ignore",
    )

    # メソッドを、引数を取らない属性のように呼び出せるようにする。
    @property
    def database_url(self) -> URL:

        # .envから取得した値を使ってSQLAlchemy用のURLを作成する。
        # URL.create()を使うと、パスワードに記号が含まれていても安全に処理できる。
        return URL.create(
            # MySQLをPyMySQLドライバー経由で操作する。
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            # MySQLとの通信で使用する文字コードを指定する。
            query={"charset": self.db_charset},
        )

    # CORSで許可するURLをリスト形式に変換する。
    @property
    def allowed_origins(self) -> list[str]:

        # split(",")：カンマ区切りの文字列を分割する。
        # strip()：URLの前後にある空白を削除する。
        # if value.strip()：空文字列になった値を除外する。
        return [
            value.strip() for value in self.cors_origins.split(",") if value.strip()
        ]


# 同じ設定オブジェクトを繰り返し作成しないように、結果をキャッシュする。
# 引数がないため、Settingsは最初の呼び出し時に一度だけ作成される。
@lru_cache
def get_settings() -> Settings:
    return Settings()


# .envから設定値を読み込み、Settingsオブジェクトを取得する。
settings = get_settings()


# データベースとの接続を管理するEngineを作成する。
# 実際の接続は、基本的に最初のSQL実行時に行われる。
engine = create_engine(
    # Settingsで作成したMySQL接続URLを指定する。
    settings.database_url,
    # 接続を使う前に有効か確認し、切断済みなら再接続する。
    pool_pre_ping=True,
    # 接続を3600秒ごとに作り直し、古い接続が残るのを防ぐ。
    pool_recycle=3600,
    # 実行したSQLをコンソールへ表示しない。
    echo=False,
    # 例外ログにSQLのパラメーター値を含めない。
    hide_parameters=True,
)


# データベース操作に使用するSessionを作成するための仕組みを定義する。
# Sessionは、取得・追加・更新・削除からcommitまでの処理単位になる。
SessionLocal = sessionmaker(
    # 作成したSessionをEngineへ接続する。
    bind=engine,
    # SQL実行前に変更内容を自動反映しない。
    autoflush=False,
    # commit後も取得済みオブジェクトの値をそのまま使用できるようにする。
    expire_on_commit=False,
)


# SQLAlchemyモデルが共通して継承する基底クラスを定義する。
# Category、Assignee、Taskなどのモデルは、このBaseを継承して作成する。
class Base(DeclarativeBase):
    pass


# 参考資料
# https://qiita.com/masa-asa/items/7bea04e4f9ba5b9ef092
# https://fastapi.tiangolo.com/ja/advanced/settings/
# https://qiita.com/inetcpl/items/b4146b9e8e1adad239d8
