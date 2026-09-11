# Assignee（担当者）の一覧取得と新規作成を担当するデータアクセス層。

# SELECT文を作成するための関数を読み込む。
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

# データベースとのやり取りに使用するSession型を読み込む。
from sqlalchemy.orm import Session

# データベースのassigneesテーブルに対応するモデルを読み込む。
from ..Model.models import Assignee

# 担当者作成時の入力データを検証するスキーマを読み込む。
from ..Model.schemas import AssigneeCreate


# 担当者をIDの昇順で一覧取得する。
def get_assignees(
    db: Session,
) -> list[Assignee]:

    # Assigneeを取得するSELECT文を作成する。
    # order_by()：IDが小さい順に並べる。
    statement = select(Assignee).order_by(Assignee.id)

    # scalars()でAssigneeオブジェクトだけを取り出す。
    # all()ですべて取得し、list()でリストに変換して返す。
    return list(db.scalars(statement).all())


# 受け取った入力データから新しい担当者を作成する。
def create_assignee(
    db: Session,
    payload: AssigneeCreate,
) -> Assignee:

    # 検証済みのnameを使ってAssigneeオブジェクトを作成する。
    assignee = Assignee(name=payload.name)

    # 新しい担当者をデータベースへの登録対象に追加する。
    db.add(assignee)

    # 変更内容をデータベースに確定する。
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    # データベースから最新の値を再取得する。
    # 自動採番されたidなどがassigneeに反映される。
    db.refresh(assignee)

    # 作成済みのAssigneeオブジェクトを返す。
    return assignee
