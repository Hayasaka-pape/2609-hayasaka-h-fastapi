# 動作確認の記録

実施日：2026-09-10（日本時間）。モックではなく、ブラウザ → FastAPI → 指定 MySQL-Sample の MySQL という構成で確認しました。

## 確認環境

- MySQL-Sample：<https://github.com/pygmalin-info/MySQL-Sample>
- 使用コミット：`70db092bc5ae322ba7f182f625b31f5916e61e63`。指定リポジトリの `compose.yaml` / `config/my.cnf` は変更していません。
- MySQL 8.0.46 / `localhost:13306` / `test_db` / `test_user` / `utf8mb4`
- MySQL は WSL Ubuntu の MySQL-Sample で `docker compose up -d` を実行。
- FastAPI 0.141.1、SQLAlchemy 2.0.52、Pydantic 2.13.5、Python 3.12.14（Windows仮想環境）
- API：`http://localhost:8888`、画面：`http://localhost:3000`
- ブラウザの実画面を撮影。幅の狭い表示でも操作できることを確認。

## 画面操作

カテゴリ「提出確認」と担当者「早坂」を画面から登録した後、次の流れを実行しました。

| 順番 | 操作と結果 | スクリーンショット |
|---|---|---|
| 1 | タイトル「提出用READMEを確認する」、説明、カテゴリ、担当者を入力。画像は説明・カテゴリ・担当者の入力部分。 | [01-create-form.png](01-create-form.png) |
| 2 | 追加を押し、一覧に未完了のタスクが1件表示される。APIは201。 | [02-created.png](02-created.png) |
| 3 | チェックを入れて完了へ変更。完了表示とチェック状態が保存される。 | [03-completed.png](03-completed.png) |
| 4 | 編集を開き、タイトルを「提出用READMEを最終確認する」、説明を「編集済み：起動手順とスクリーンショットの対応を確認する。」に変更。 | [04-edit-form.png](04-edit-form.png) |
| 5 | 変更を保存。完了状態・カテゴリ・担当者を維持して新しい内容が表示される。 | [05-edited.png](05-edited.png) |
| 6 | FastAPIを停止し、MySQLを `docker compose down` → `docker compose up -d` で再作成。その後FastAPIを起動し、ブラウザを再読み込み。同じID・編集内容・関連・完了状態・作成更新日時が残る。 | [06-after-restart.png](06-after-restart.png) |
| 7 | 削除を押し、すべての状態・すべてのカテゴリで0件になる。DELETEは204、そのIDのGETは404、MySQLの行数は0。 | [07-deleted.png](07-deleted.png) |
| 8 | カテゴリ「提出確認」をもう一度追加。409が返り、モーダル内に重複エラーが見える。 | [08-duplicate-validation.png](08-duplicate-validation.png) |

## APIとMySQLの確認

再起動前後にAPIのレスポンスを取得し、SQLで `tasks` の同じ行を直接読み取りました。結果を [verification.json](verification.json) に保存しています。

- `tasks` / `categories` / `assignees` の3テーブルが存在。
- `is_done=true`、`is_done=false`、状態とカテゴリのAND条件、存在しないカテゴリの空配列を確認。
- `localhost:3000` と `127.0.0.1:3000` の両オリジンで POST / PUT / DELETE のプリフライトが200。
- 存在しないタスクは404、不正なIDや状態クエリは422、`/docs` は200。
- 再起動前後のAPIレスポンスが完全に一致。
- 画面のCRUD確認中、ブラウザのエラーログは0件（意図した重複409テストの前に取得）。

実際のHTTP応答の抜粋は [api-verification.txt](api-verification.txt) を参照してください。

## 自動テストとの区別

`fastapi_app` で `python -m pytest -q` を実行し、**41件が成功**しました。自動テストはリクエストごとのDB処理も通し、テスト用SQLiteへ接続します。MySQLの実接続とコンテナ再作成後の永続化は、上記の実機確認で別途検証しています。

検証に使ったタスクは画面の削除操作で削除済みです。カテゴリ・担当者は動作確認用データとして残っています。確認終了後はFastAPI・フロントエンドを停止し、MySQL-Sampleで `docker compose down` を実行しました。3000 / 8888 の待受終了、MySQLコンテナの停止・削除、`servlet-mysql_servlet-mysql-store` ボリュームの保持を確認済みです。`-v` は使用していません。
