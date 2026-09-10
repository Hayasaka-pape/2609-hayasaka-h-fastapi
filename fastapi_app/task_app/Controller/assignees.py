"""担当者に関するAPIのエンドポイントを定義する場所。

- GET /assignees：担当者を一覧取得する。
- POST /assignees：担当者を新規作成する。
"""

# APIルーター、HTTPエラー、HTTPステータスコードを読み込む。
from fastapi import APIRouter, HTTPException, status

# UNIQUE制約など、データの整合性に違反した場合の例外を読み込む。
from sqlalchemy.exc import IntegrityError

# 担当者のデータベース操作を行うデータアクセス層を読み込む。
# assignee_dalという別名を付け、役割を分かりやすくする。
from ..DataAccessLayer import assignees as assignee_dal

# リクエストごとのデータベースSessionを受け取る型を読み込む。
from ..dependencies import DbSession

# リクエストとレスポンスのデータ形式を読み込む。
from ..Model.schemas import AssigneeCreate, AssigneeResponse

# 担当者API用のルーターを作成する。
router = APIRouter(
    # このルーターのURLには、先頭に/assigneesが付く。
    prefix="/assignees",
    # Swagger UIでassigneesグループとして表示する。
    tags=["assignees"],
)


# GET /assigneesを定義する。
@router.get(
    # prefixと組み合わせて「/assignees」になる。
    "",
    # レスポンスがAssigneeResponseのリストであることを指定する。
    response_model=list[AssigneeResponse],
)
def list_assignees(
    # FastAPIの依存性注入によってSessionを受け取る。
    db: DbSession,
):
    # データアクセス層へ一覧取得処理を依頼し、その結果を返す。
    return assignee_dal.get_assignees(db)


# POST /assigneesを定義する。
@router.post(
    # prefixと組み合わせて「/assignees」になる。
    "",
    # 作成した担当者をAssigneeResponse形式で返す。
    response_model=AssigneeResponse,
    # 作成成功時のHTTPステータスコードを201にする。
    status_code=status.HTTP_201_CREATED,
)
def create_assignee(
    # リクエスト本文をAssigneeCreateで検証して受け取る。
    payload: AssigneeCreate,
    # FastAPIの依存性注入によってSessionを受け取る。
    db: DbSession,
):
    try:
        # データアクセス層へ担当者の作成処理を依頼する。
        return assignee_dal.create_assignee(db, payload)

    # 名前の重複など、データベースの制約違反を処理する。
    except IntegrityError:
        # 失敗したトランザクションを取り消し、
        # Sessionを再び使用できる状態に戻す。
        db.rollback()

        # 同じ名前がすでに存在することを409エラーとして返す。
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignee name already exists",
        )
