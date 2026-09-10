"""APIのリクエスト・レスポンスを表すPydanticスキーマ。

- FastAPIが受け取るデータと返すデータの形式を定義する。
- 入力値の型、文字数、IDの範囲を検証する。
- 空白だけのnameとtitleを拒否する。
- SQLAlchemyのモデルからレスポンス用のデータを読み取る。
"""

# 作成日時と更新日時を表す型を読み込む。
from datetime import datetime

# 基本の型に、検証ルールなどの追加情報を付けるために使用する。
from typing import Annotated

# BaseModel：データの型や値を検証するスキーマの基底クラス。
# ConfigDict：スキーマの動作を設定する。
# Field：文字数や数値の範囲などの制約を指定する。
# field_validator：特定の項目に独自の検証・変換処理を追加する。
from pydantic import BaseModel, ConfigDict, Field, field_validator

# 複数のスキーマで使う検証ルールを共通化する。
Name = Annotated[str, Field(min_length=1, max_length=100)]  # 名前は1～100文字。
Title = Annotated[str, Field(min_length=1, max_length=255)]  # タイトルは1～255文字。
PositiveId = Annotated[int, Field(gt=0)]  # gtは「より大きい」を表し、0以下を拒否する。
Description = Annotated[str, Field(max_length=2000)]

# PositiveIdは数値の範囲を検証するだけで、DB上にそのIDが存在するかは確認しない。


# カテゴリー作成時の入力項目を定義する。
class CategoryCreate(BaseModel):
    name: Name  # 既定値がないため、nameの指定は必須である。

    # 文字数を検証する前に前後の空白を除き、空白だけの入力を拒否できるようにする。
    @field_validator(
        "name", mode="before"
    )  # Pydanticの通常の型・制約検証より先に実行する。
    @classmethod  # インスタンスではなくクラスを、第1引数clsとして受け取る。
    def strip_name(cls, value):
        # isinstance()で文字列か確認し、それ以外は通常の型検証へ渡す。
        # 「A if 条件 else B」は、条件がTrueならA、FalseならBを返す式である。
        return (
            value.strip() if isinstance(value, str) else value
        )  # strip()は前後の空白を除く。

        # 例："  仕事  "は"仕事"になる。文字列の途中の空白は残る。
        # "   "は""になり、その後のmin_length=1の検証で拒否される。


# カテゴリーを返すときの出力項目を定義する。
class CategoryResponse(BaseModel):
    # 辞書だけでなく、category.idやcategory.nameなどの属性から値を読み取る。
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# 担当者作成時の入力項目を定義する。
class AssigneeCreate(BaseModel):
    name: Name

    # 名前の前後の空白を除いてから、型と文字数を検証する。
    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return (
            value.strip() if isinstance(value, str) else value
        )  # 文字列の場合だけ整形する。


# 担当者を返すときの出力項目を定義する。
class AssigneeResponse(BaseModel):
    # Assigneeモデルの属性からidとnameを読み取れるようにする。
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# タスクの作成・更新で共通する入力項目と検証処理をまとめる。
class TaskBase(BaseModel):
    title: Title  # 必須項目とし、1～255文字に制限する。

    # タイトルの前後の空白を除き、空白だけなら文字数の検証で拒否する。
    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        return value.strip() if isinstance(value, str) else value


# タスク作成時の入力項目を定義する。
# TaskBaseを継承し、titleとその検証処理を引き継ぐ。
class TaskCreate(TaskBase):
    # 「| None」はNoneを許可し、「= None」は省略時の値を指定する。
    description: Description | None = None

    # カテゴリーと担当者は未設定を許可する。
    # 指定する場合は、0より大きい整数である必要がある。
    category_id: PositiveId | None = None
    assignee_id: PositiveId | None = None


# タスク更新時の入力項目を定義する。
# TaskBaseから継承したtitleと、ここで定義するis_doneを必須にする。
class TaskUpdate(TaskBase):
    is_done: bool  # 完了状態を受け取る。既定値がないため省略できない。

    # PUTは全項目の置き換え。関連や説明を解除するときも明示的にnullを送る。
    # 省略を拒否し、値の送り忘れによる意図しない関連解除を防ぐ。
    description: Description | None
    category_id: PositiveId | None
    assignee_id: PositiveId | None


# タスクを返すときの出力項目を定義する。
# 作成・更新用とは分け、ID、関連データ、日時も返せるようにする。
class TaskResponse(BaseModel):
    # Taskモデルの属性から、各項目の値を読み取れるようにする。
    model_config = ConfigDict(from_attributes=True)

    # タスクの基本情報を返す。
    id: int
    title: str

    # Noneを許可するが、既定値がないため検証時には項目自体が必要である。
    # JSONとして返す際、Noneはnullになる。
    description: str | None

    is_done: bool

    # IDだけでなく、idとnameを含む関連データを入れ子にして返す。
    # 例："category": {"id": 1, "name": "仕事"}
    # 関連付けがない場合はnullを返す。
    category: CategoryResponse | None
    assignee: AssigneeResponse | None

    # 作成日時と更新日時を返す。このスキーマ自体は日時を生成しない。
    created_at: datetime
    updated_at: datetime
