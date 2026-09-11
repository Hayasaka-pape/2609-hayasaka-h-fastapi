"""Task / Category / AssigneeのSQLAlchemy ORMモデル。

- Pythonのクラスとデータベースのテーブルを対応付ける。
- 各テーブルの列、制約、モデル同士の関連を定義する。
- カテゴリーや担当者を削除しても、タスク自体は残す。
- タスクの作成日時と更新日時を記録する。

参考：
https://zenn.dev/sh0nk/books/537bb028709ab9/viewer/281ee0
"""

# Python側で日時を表す型を読み込む。
from datetime import datetime

# データベースの列の型、外部キー、SQL関数などを読み込む。
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text

# Mapped：ORMが管理する属性の型を示す。
# mapped_column()：テーブルの列と制約を定義する。
# relationship()：関連するモデルをオブジェクトとして扱えるようにする。
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 各モデルで共通して継承する基底クラスを読み込む。
from ..DataAccessLayer.database import Base


# カテゴリーを管理するモデル。
# 1つのカテゴリーに複数のタスクを関連付ける。
class Category(Base):
    __tablename__ = "categories"  # 対応するテーブル名を指定する。

    # 各カテゴリーを一意に識別するIDを定義する。
    id: Mapped[int] = mapped_column(
        primary_key=True,  # 主キーにする。この整数主キーは通常、自動採番される。
    )

    # 同じカテゴリー名の重複とNULLを禁止する。
    name: Mapped[str] = mapped_column(
        String(100),  # 最大100文字の文字列を格納する列にする。
        unique=True,  # 同じ値の重複を禁止する。
        nullable=False,  # NULLを禁止する。空文字の禁止とは異なる。
    )

    # category.tasksで、このカテゴリーに属するタスクのリストを扱う。
    # "Task"は、後で定義するクラスを文字列で参照する書き方である。
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="category",  # Task.categoryと対になる関連を指定する。
        # カテゴリー削除時、未読込のタスクを取得せず、
        # 外部キーをNULLにする処理をDB側のON DELETE SET NULLに任せる。
        # 読込済みのタスクについては、ORMが外部キーをNULLにする。
        passive_deletes=True,
    )


# 担当者を管理するモデル。
# 1人の担当者に複数のタスクを関連付ける。
class Assignee(Base):
    __tablename__ = "assignees"

    # 各担当者を一意に識別するIDを定義する。
    id: Mapped[int] = mapped_column(primary_key=True)

    # 担当者名を最大100文字で保存し、重複とNULLを禁止する。
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    # assignee.tasksで、この担当者が受け持つタスクのリストを扱う。
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="assignee",  # Task.assigneeと対になる関連を指定する。
        passive_deletes=True,  # 削除時の未読込タスクの処理をDBへ任せる。
    )


# タスクの内容、完了状態、カテゴリー、担当者、日時を管理するモデル。
class Task(Base):
    __tablename__ = "tasks"

    # 各タスクを一意に識別するIDを定義する。
    id: Mapped[int] = mapped_column(primary_key=True)

    # タイトルを最大255文字で保存し、NULLを禁止する。
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # 詳細説明は任意項目とし、未設定を許可する。
    # str | Noneは、Python側で文字列またはNoneを扱うことを示す。
    description: Mapped[str | None] = mapped_column(
        Text,  # 長い文章を保存するための列の型を指定する。
        nullable=True,  # DB側でNULLを許可する。PythonではNoneに対応する。
    )

    # 完了状態を保存する。値を省略して登録した場合は未完了にする。
    is_done: Mapped[bool] = mapped_column(
        Boolean,  # Python側ではTrueまたはFalseとして扱う。
        nullable=False,
        default=False,  # SQLAlchemy経由のINSERT時に補う既定値を指定する。
        server_default=text("0"),  # DB側にも既定値0を設定する。text()はSQL式を表す。
        index=True,  # 完了状態での検索に利用できるインデックスを作る。
    )

    # 所属カテゴリーのIDを保存する。未分類のタスクも許可する。
    # ForeignKeyは、指定したIDが参照先のテーブルに存在することを要求する。
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "categories.id",  # categoriesテーブルのid列を参照する。
            ondelete="SET NULL",  # カテゴリー削除時は、このIDだけをNULLにする。
        ),
        nullable=True,
        index=True,  # カテゴリーIDでの検索に利用できるインデックスを作る。
    )

    # 担当者のIDを保存する。担当者が未設定のタスクも許可する。
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "assignees.id",
            ondelete="SET NULL",  # 担当者削除時もタスクは残し、このIDをNULLにする。
        ),
        nullable=True,
        index=True,
    )

    # 作成日時を保存する。INSERTで省略された場合はDBの現在日時を使う。
    created_at: Mapped[datetime] = mapped_column(
        DateTime,  # DB側の日時型を指定する。
        nullable=False,
        server_default=func.now(),  # func.now()は現在日時を取得するSQL式を作る。
    )

    # 作成時には現在日時を設定し、更新時には更新日時を記録する。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        # SQLAlchemyがUPDATEを実行するとき、この列の値が未指定なら
        # 現在日時を設定する。DBへ直接書いたSQLまで自動更新する設定ではない。
        onupdate=func.now(),
    )

    # category_idはIDの数値、categoryは関連するCategoryオブジェクトを表す。
    # relationship()自体はDBの列を追加しない。
    # 例：task.category.nameでカテゴリー名を参照できる。
    # 未分類の場合はNoneなので、属性へアクセスする前に確認する。
    category: Mapped[Category | None] = relationship(
        back_populates="tasks",  # Category.tasksと対になる関連を指定する。
    )

    # task.assigneeで担当者オブジェクトを扱う。担当者が未設定ならNoneになる。
    assignee: Mapped[Assignee | None] = relationship(
        back_populates="tasks",  # Assignee.tasksと対になる関連を指定する。
    )
