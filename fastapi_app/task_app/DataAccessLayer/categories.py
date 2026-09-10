# Category（カテゴリー）の一覧取得と新規作成を担当するデータアクセス層。

# SELECT文を作成するための関数を読み込む。
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

# データベースとのやり取りに使用するSession型を読み込む。
from sqlalchemy.orm import Session

# categoriesテーブルに対応するCategoryモデルを読み込む。
from ..Model.models import Category

# カテゴリー作成時の入力データを検証するスキーマを読み込む。
from ..Model.schemas import CategoryCreate


# カテゴリーをIDの昇順で一覧取得する。
def get_categories(
    db: Session,
) -> list[Category]:

    # Categoryを取得するSELECT文を作成する。
    # order_by()：IDが小さい順に並べる。
    statement = select(Category).order_by(Category.id)

    # scalars()でCategoryオブジェクトだけを取り出す。
    # all()ですべて取得し、list()でリストに変換して返す。
    return list(db.scalars(statement).all())


# 受け取った入力データから新しいカテゴリーを作成する。
def create_category(
    db: Session,
    payload: CategoryCreate,
) -> Category:

    # 検証済みのnameを使ってCategoryオブジェクトを作成する。
    category = Category(name=payload.name)

    # 新しいカテゴリーをデータベースへの登録対象に追加する。
    db.add(category)

    # 変更内容をデータベースに確定する。
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    # データベースから最新の値を再取得する。
    # 自動採番されたidなどがcategoryに反映される。
    db.refresh(category)

    # 作成済みのCategoryオブジェクトを返す。
    return category
