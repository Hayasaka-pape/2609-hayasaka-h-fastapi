"""タスクに関するAPIのエンドポイントを定義する場所。

- GET /tasks：タスクを一覧取得する。
- GET /tasks/{task_id}：タスクを1件取得する。
- POST /tasks：タスクを新規作成する。
- PUT /tasks/{task_id}：タスクを更新する。
- DELETE /tasks/{task_id}：タスクを削除する。
"""

# APIルーター、HTTPエラー、レスポンス、ステータスコードを読み込む。
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response, status

# Taskに関するデータベース操作をデータアクセス層から読み込む。
from ..DataAccessLayer.tasks import (
    delete_task_data,
    find_task,
    find_tasks,
    save_task,
    update_task_data,
)

# FastAPIの依存性注入でデータベースSessionを受け取るための型を読み込む。
from ..dependencies import DbSession

# データベースのテーブルに対応するモデルを読み込む。
from ..Model.models import Assignee, Category, Task

# リクエストとレスポンスのデータ形式を読み込む。
from ..Model.schemas import TaskCreate, TaskResponse, TaskUpdate

# タスクAPI専用のルーターを作成する。
router = APIRouter(
    # このルーターに定義したURLの先頭へ/tasksを付ける。
    prefix="/tasks",
    # Swagger UIでtasksグループとして表示する。
    tags=["tasks"],
)


# GET /tasksを定義する。
@router.get(
    "",
    # TaskResponse形式のリストをレスポンスとして返す。
    response_model=list[TaskResponse],
)
def list_tasks(
    # リクエストごとのデータベースSessionを受け取る。
    db: DbSession,
    # 完了状態による絞り込み条件を受け取る。
    # 「bool | None」は、True・False・未指定のいずれかを表す。
    is_done: bool | None = None,
    # カテゴリーIDによる絞り込み条件を受け取る。
    category_id: Annotated[int | None, Query(gt=0)] = None,
):
    # データアクセス層へタスクの一覧取得を依頼する。
    return find_tasks(
        db,
        is_done=is_done,
        category_id=category_id,
    )


# GET /tasks/{task_id}を定義する。
# {task_id}の部分には、取得したいタスクのIDが入る。
@router.get(
    "/{task_id}",
    response_model=TaskResponse,
)
def get_task(
    task_id: Annotated[int, Path(gt=0)],
    db: DbSession,
):
    # IDを使って、関連データを含むタスクを検索する。
    task = find_task(db, task_id)

    # 該当するタスクが存在しない場合は404エラーを返す。
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    # 見つかったタスクを返す。
    return task


# 指定されたCategoryやAssigneeが存在するか確認する共通関数。
def require_reference(
    db,
    model,
    value,
    label,
):
    # valueがNoneでない場合だけ、IDに対応するデータを検索する。
    # andには、左側がTrueのときだけ右側を評価する短絡評価がある。
    if value is not None and db.get(model, value) is None:
        # 関連データが存在しない場合は404エラーを返す。
        # f文字列を使い、CategoryまたはAssigneeをメッセージへ埋め込む。
        raise HTTPException(
            status_code=404,
            detail=f"{label} not found",
        )


# POST /tasksを定義する。
@router.post(
    "",
    # 作成したタスクをTaskResponse形式で返す。
    response_model=TaskResponse,
    # 作成成功時のHTTPステータスコードを201にする。
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    # リクエスト本文をTaskCreateで検証して受け取る。
    payload: TaskCreate,
    db: DbSession,
):
    # 指定されたカテゴリーが存在するか確認する。
    require_reference(
        db,
        Category,
        payload.category_id,
        "Category",
    )

    # 担当者IDが指定されている場合は、その担当者が存在するか確認する。
    require_reference(
        db,
        Assignee,
        payload.assignee_id,
        "Assignee",
    )

    # model_dump()でPydanticモデルを辞書へ変換する。
    # データアクセス層へタスクの保存を依頼する。
    return save_task(
        db,
        payload.model_dump(),
    )


# PUT /tasks/{task_id}を定義する。
@router.put(
    "/{task_id}",
    response_model=TaskResponse,
)
def update_task(
    # 更新するタスクのIDをURLから受け取る。
    task_id: Annotated[int, Path(gt=0)],
    # 更新内容をTaskUpdateで検証して受け取る。
    payload: TaskUpdate,
    # リクエストごとのデータベースSessionを受け取る。
    db: DbSession,
):
    # 主キーであるtask_idを使ってタスクを取得する。
    # db.get()は、モデルと主キーを指定して1件取得するメソッドである。
    task = db.get(Task, task_id)

    # 更新対象のタスクが存在しない場合は404エラーを返す。
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    # 更新後に設定するカテゴリーが存在するか確認する。
    require_reference(
        db,
        Category,
        payload.category_id,
        "Category",
    )

    # 更新後に設定する担当者が存在するか確認する。
    require_reference(
        db,
        Assignee,
        payload.assignee_id,
        "Assignee",
    )

    # 更新内容を辞書へ変換し、データアクセス層へ渡す。
    return update_task_data(
        db,
        task,
        payload.model_dump(),
    )


# DELETE /tasks/{task_id}を定義する。
@router.delete(
    "/{task_id}",
    # 削除成功時のHTTPステータスコードを204にする。
    status_code=status.HTTP_204_NO_CONTENT,
    # JSONではなく、本文を持たない通常のResponseを使用する。
    response_class=Response,
)
def delete_task(
    task_id: Annotated[int, Path(gt=0)],
    db: DbSession,
) -> Response:
    # 主キーであるtask_idを使って削除対象を取得する。
    task = db.get(Task, task_id)

    # 削除対象が存在しない場合は404エラーを返す。
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    # データアクセス層へタスクの削除を依頼する。
    delete_task_data(db, task)

    # 204はレスポンス本文がないことを表す。
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
