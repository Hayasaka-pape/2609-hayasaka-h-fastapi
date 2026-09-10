"""APIにデータベースSessionを渡し、使用後に後片付けする場所。

- get_db：Sessionを作成し、処理終了時に閉じる。
- DbSession：Sessionの型情報と依存性注入の指定をまとめる。
"""

# yieldを使うジェネレーター関数の型ヒントに使用する。
from collections.abc import Generator

# 型に追加情報を付けるために使用する。
from typing import Annotated

# 必要な値をFastAPIに用意してもらう「依存性注入」に使用する。
from fastapi import Depends

# データベース操作を行うSessionの型を読み込む。
from sqlalchemy.orm import Session

# 設定済みのSessionを作成するための仕組みを読み込む。
from .DataAccessLayer.database import SessionLocal


# APIで使用するSessionを用意し、使用後の後片付けも担当する。
# Generator[Session, None, None]の各要素は、次の型を表す。
# Session：yieldで渡す値の型。
# None：外部からsend()で受け取る値を想定しない。
# None：ジェネレーター終了時にreturnで返す値がない。
def get_db() -> Generator[Session, None, None]:
    # 新しいSessionを作成する。この時点で必ずDBへ接続するわけではない。
    db = SessionLocal()

    try:
        # SessionをFastAPIへ渡し、ここで関数の実行を一時停止する。
        # returnと異なり、後で処理を再開して後片付けできる。
        yield db

    except Exception:
        # 読み取り・保存後の再取得も含め、失敗したリクエストを取り消す。
        db.rollback()
        raise

    finally:
        # 依存関係の後片付け時に、正常終了・例外発生のどちらでも実行する。
        # Sessionが使用している接続などのリソースを解放する。
        # close()は保存の確定ではない。保存には別途commit()が必要になる。
        db.close()


# API関数で繰り返す型指定と依存性注入の設定を、1つの名前にまとめる。
# Session：API関数が受け取るdbの型を示す。
# Depends(get_db)：get_dbをFastAPIが管理し、yieldされたSessionを渡す。
# get_db()と書かず関数自体を渡し、実行の管理をFastAPIに任せる。
DbSession = Annotated[Session, Depends(get_db)]

# 使用例：API関数の引数を「db: DbSession」とする。
# FastAPIがSessionの受け渡しとget_dbの後片付けを管理するため、
# API関数ごとにSessionの作成・close処理を書く必要がなくなる。
