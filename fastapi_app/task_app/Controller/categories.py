"""カテゴリーに関するAPIのエンドポイントを定義する場所。

- GET /categories：カテゴリーを一覧取得する。
- POST /categories：カテゴリーを新規作成する。
"""

# APIルーター、HTTPエラー、HTTPステータスコードを読み込む。
from fastapi import APIRouter, HTTPException, status

# データベースの制約違反が発生したときの例外を読み込む。
from sqlalchemy.exc import IntegrityError

# カテゴリーのデータベース操作を担当するモジュールを読み込む。
# category_dalという別名を付けて、役割を明確にする。
from ..DataAccessLayer import categories as category_dal

# FastAPIの依存性注入でデータベースSessionを受け取るための型を読み込む。
from ..dependencies import DbSession

# 入力データと出力データの形式を定義したスキーマを読み込む。
from ..Model.schemas import CategoryCreate, CategoryResponse

# カテゴリーAPI専用のルーターを作成する。
router = APIRouter(
    # このルーターに定義したURLの先頭へ/categoriesを付ける。
    prefix="/categories",
    # Swagger UIでcategoriesグループとして表示する。
    tags=["categories"],
)


# GET /categoriesを定義する。
@router.get(
    # prefixと組み合わせて「/categories」になる。
    "",
    # CategoryResponse形式のリストをレスポンスとして返す。
    response_model=list[CategoryResponse],
)
def list_categories(
    # リクエストごとのデータベースSessionを受け取る。
    db: DbSession,
):
    # データアクセス層へカテゴリーの一覧取得を依頼する。
    return category_dal.get_categories(db)


# POST /categoriesを定義する。
@router.post(
    # prefixと組み合わせて「/categories」になる。
    "",
    # 作成したカテゴリーをCategoryResponse形式で返す。
    response_model=CategoryResponse,
    # 作成成功時のHTTPステータスコードを201にする。
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    # リクエスト本文をCategoryCreateで検証して受け取る。
    payload: CategoryCreate,
    # リクエストごとのデータベースSessionを受け取る。
    db: DbSession,
):
    try:
        # データアクセス層へカテゴリーの作成を依頼する。
        return category_dal.create_category(db, payload)

    # 名前の重複など、データベースの制約に違反した場合に実行する。
    except IntegrityError:
        # 失敗したデータベース操作を取り消す。
        # rollback後は同じSessionを再び使用できるようになる。
        db.rollback()

        # 名前が重複していることをHTTP 409エラーとして返す。
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category name already exists",
        )
