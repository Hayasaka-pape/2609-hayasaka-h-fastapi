"""Taskに関するデータベース操作を担当するデータアクセス層。

- 条件に合うタスクの一覧取得
- IDを指定したタスクの取得
- タスクの新規作成
- タスクの更新
- タスクの削除
"""

# SELECT文を作成するための関数を読み込む。
from sqlalchemy import select

# SQLAlchemyで発生するデータベース関連の例外を読み込む。
from sqlalchemy.exc import SQLAlchemyError

# 関連データを追加のSELECT文でまとめて読み込む機能を読み込む。
from sqlalchemy.orm import selectinload

# tasksテーブルに対応するTaskモデルを読み込む。
from ..Model.models import Task

# Taskと一緒にCategoryとAssigneeも取得する共通のSELECT文を作成する。
# selectinload()を使うことで、タスクごとにSQLが繰り返されるN+1問題を防ぐ。
TASK_WITH_RELATIONS = select(Task).options(
    selectinload(Task.category),
    selectinload(Task.assignee),
)


# 条件に合うタスクを一覧取得する。
def find_tasks(
    db,
    # *以降の引数は、名前を指定して渡す必要がある。
    *,
    is_done=None,
    category_id=None,
):
    # 関連データを含む共通のSELECT文を使用する。
    statement = TASK_WITH_RELATIONS

    # is_doneが指定されている場合だけ、完了状態で絞り込む。
    # 「is not None」により、Falseが指定された場合も正しく処理できる。
    if is_done is not None:
        statement = statement.where(Task.is_done == is_done)

    # category_idが指定されている場合だけ、カテゴリーで絞り込む。
    if category_id is not None:
        statement = statement.where(Task.category_id == category_id)

    # 作成日時が新しい順に並べる。
    # 作成日時が同じ場合は、IDが大きいタスクを先に並べる。
    statement = statement.order_by(
        Task.created_at.desc(),
        Task.id.desc(),
    )

    # scalars()でTaskオブジェクトだけを取り出す。
    # all()で条件に合うすべてのタスクを取得する。
    return db.scalars(statement).all()


# IDを指定してタスクを1件取得する。
def find_task(db, task_id: int):
    # Task.idがtask_idと一致する、という検索条件を追加する。
    statement = TASK_WITH_RELATIONS.where(Task.id == task_id).execution_options(
        # 外部キー更新後も、Sessionに残る変更前の関連を返さずDBから読み直す。
        populate_existing=True,
    )

    # scalar()で最初のTaskオブジェクトを取得する。
    # 該当するタスクが存在しない場合はNoneを返す。
    return db.scalar(statement)


# 新しいタスクをデータベースへ保存する。
def save_task(db, values: dict):
    # **valuesで辞書の各要素をキーワード引数としてTaskへ渡す。
    # 例：{"title": "勉強"} → Task(title="勉強")
    # 新しいタスクの完了状態は必ずFalseにする。
    task = Task(
        **values,
        is_done=False,
    )

    # 新しいTaskをデータベースへの登録対象に追加する。
    db.add(task)

    try:
        # INSERTを実行し、変更内容をデータベースへ確定する。
        db.commit()

    # データベース処理に失敗した場合の処理。
    except SQLAlchemyError:
        # 失敗した変更を取り消し、Sessionを再利用できる状態に戻す。
        db.rollback()

        # 発生した例外を呼び出し元へそのまま渡す。
        raise

    # 保存したタスクを関連データ付きで取得して返す。
    return find_task(db, task.id)


# 既存タスクのデータを更新する。
def update_task_data(
    db,
    task: Task,
    values: dict,
):
    # 更新するフィールド名と値を1組ずつ取り出す。
    for field, value in values.items():

        # setattr()で、フィールド名を文字列で指定して値を変更する。
        # 例：setattr(task, "title", "買い物")はtask.title = "買い物"と同じ。
        setattr(task, field, value)

    try:
        # Taskの変更内容をUPDATE文でデータベースへ反映する。
        db.commit()

    # データベース処理に失敗した場合の処理。
    except SQLAlchemyError:
        # 更新前の状態へ戻し、Sessionを再利用できる状態にする。
        db.rollback()

        # 発生した例外を呼び出し元へそのまま渡す。
        raise

    # 更新後のタスクを関連データ付きで取得して返す。
    return find_task(db, task.id)


# 指定されたタスクをデータベースから削除する。
def delete_task_data(db, task: Task):
    # Taskをデータベースから削除する対象として登録する。
    db.delete(task)

    try:
        # DELETEを実行し、削除をデータベースへ確定する。
        db.commit()

    # データベース処理に失敗した場合の処理。
    except SQLAlchemyError:
        # 削除処理を取り消し、Sessionを再利用できる状態にする。
        db.rollback()

        # 発生した例外を呼び出し元へそのまま渡す。
        raise
