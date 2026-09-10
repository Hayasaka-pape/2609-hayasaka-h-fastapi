# フロントエンドの読み方

このフロントエンドは、React / Vue を使わない HTML + CSS + JavaScript の SPA です。

## ファイルの役割

- `index.html`: 入力欄、一覧、編集・カテゴリ・担当者の3モーダル
- `css/style.css`: レイアウト、完了表示、モーダル、スマートフォン対応
- `js/api.js`: `fetch` と FastAPI の9エンドポイント
- `js/app.js`: 画面状態、イベント、DOM の再描画

HTML、CSS、JavaScript には、セクションや API との境界が分かる日本語コメントを入れています。

## API 対応

| 操作 | JavaScript | FastAPI |
|---|---|---|
| 初期表示 | `getTasks()` | `GET /tasks` |
| タスク追加 | `createTask()` | `POST /tasks` |
| 編集前の取得 | `getTask()` | `GET /tasks/{id}` |
| 完了切替・編集保存 | `updateTask()` | `PUT /tasks/{id}` |
| 削除 | `deleteTask()` | `DELETE /tasks/{id}` |
| カテゴリ選択肢 | `getCategories()` | `GET /categories` |
| カテゴリ追加 | `createCategory()` | `POST /categories` |
| 担当者選択肢 | `getAssignees()` | `GET /assignees` |
| 担当者追加 | `createAssignee()` | `POST /assignees` |

絞り込みもブラウザ内だけで行わず、`GET /tasks?is_done=...&category_id=...` を呼びます。

## 起動

FastAPI を `http://localhost:8888` で起動してから、このフォルダで次を実行します。

WSL / macOS:

```bash
python3 -m http.server 3000
```

Windows PowerShell:

```powershell
py -m http.server 3000
```

<http://localhost:3000> を開いてください。API のポートを変える場合は `js/api.js` の `API_BASE_URL` を変更します。

## 実装上の重要点

- HTML の `select.value` は文字列なので、ID を `Number` に変換する。
- 未設定は空文字でなく JSON の `null` を送る。
- GET レスポンスの `category` / `assignee` はオブジェクトだが、POST / PUT は ID を送る。
- 完了チェックも PUT なので、`is_done` だけでなくタスクの5項目を送る。
- 204 の DELETE 応答は本文がないため、`response.json()` を呼ばない。
- API の文字列は `innerHTML` でなく `textContent` で表示する。
- カテゴリ追加後は新規用・編集用・絞り込み用の3選択欄を更新する。
- 担当者追加後は新規用・編集用の2選択欄を更新する。
- 再読み込みではタスクとカテゴリ・担当者の選択肢を再取得する。
- 登録・編集ダイアログでの API エラーは、開いているダイアログ内に表示する。
- 保存後の一覧取得に失敗した場合は、保存済みであることと再取得の失敗を表示する。
