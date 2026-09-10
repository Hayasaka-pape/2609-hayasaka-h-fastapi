"""タスク管理 API の受け入れ条件と、失敗時のデータ保護を確認する。"""

from datetime import datetime

import pytest
from sqlalchemy.exc import OperationalError


def create(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def full_update(task, **changes):
    payload = {
        "title": task["title"],
        "description": task["description"],
        "is_done": task["is_done"],
        "category_id": task["category"]["id"] if task["category"] else None,
        "assignee_id": task["assignee"]["id"] if task["assignee"] else None,
    }
    return {**payload, **changes}


def test_task_lifecycle_with_japanese_relations(client):
    category = create(client, "/categories", {"name": "  仕事  "})
    assignee = create(client, "/assignees", {"name": "  早坂  "})
    assert category["name"] == "仕事"
    assert assignee["name"] == "早坂"

    task = create(client, "/tasks", {
        "title": "  提出資料をまとめる  ",
        "description": "日本語の保存確認 📝",
        "category_id": category["id"],
        "assignee_id": assignee["id"],
    })
    assert task["title"] == "提出資料をまとめる"
    assert task["description"] == "日本語の保存確認 📝"
    assert task["is_done"] is False
    assert task["category"] == category
    assert task["assignee"] == assignee
    datetime.fromisoformat(task["created_at"])
    datetime.fromisoformat(task["updated_at"])
    path = f"/tasks/{task['id']}"
    assert client.get(path).json() == task
    assert client.get("/tasks").json() == [task]

    done = client.put(path, json=full_update(task, is_done=True))
    assert done.status_code == 200
    assert done.json()["is_done"] is True
    assert client.get(path).json()["is_done"] is True

    edited = client.put(path, json=full_update(
        done.json(), title="提出資料を更新", description="編集後の説明",
    ))
    assert edited.status_code == 200
    assert edited.json()["title"] == "提出資料を更新"
    assert client.get(path).json()["description"] == "編集後の説明"
    assert edited.json()["created_at"] == task["created_at"]

    deleted = client.delete(path)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(path).status_code == 404
    assert client.get("/tasks").json() == []
    assert client.get("/categories").json() == [category]
    assert client.get("/assignees").json() == [assignee]


def test_optional_fields_and_reference_replacement_then_removal(client):
    task = create(client, "/tasks", {"title": "関連を変更"})
    assert task["description"] is None
    assert task["category"] is None
    assert task["assignee"] is None
    path = f"/tasks/{task['id']}"

    for number in (1, 2):
        category = create(client, "/categories", {"name": f"カテゴリ{number}"})
        assignee = create(client, "/assignees", {"name": f"担当者{number}"})
        response = client.put(path, json=full_update(
            task, description="説明あり", category_id=category["id"],
            assignee_id=assignee["id"],
        ))
        assert response.status_code == 200
        task = response.json()
        assert task["category"] == category
        assert task["assignee"] == assignee
        assert client.get(path).json() == task

    response = client.put(path, json=full_update(
        task, description=None, category_id=None, assignee_id=None,
    ))
    assert response.status_code == 200
    assert response.json()["category"] is None
    assert response.json()["assignee"] is None
    assert response.json()["description"] is None
    assert client.get(path).json() == response.json()


def test_filters_include_false_and_combine_with_and(client):
    first = create(client, "/categories", {"name": "仕事"})
    second = create(client, "/categories", {"name": "私用"})
    unfinished = create(client, "/tasks", {"title": "未完了の仕事", "category_id": first["id"]})
    finished = create(client, "/tasks", {"title": "完了した仕事", "category_id": first["id"]})
    personal = create(client, "/tasks", {"title": "未完了の私用", "category_id": second["id"]})
    response = client.put(f"/tasks/{finished['id']}", json=full_update(finished, is_done=True))
    assert response.status_code == 200

    def ids(**params):
        result = client.get("/tasks", params=params)
        assert result.status_code == 200
        return [task["id"] for task in result.json()]

    assert ids() == [personal["id"], finished["id"], unfinished["id"]]
    assert ids(is_done="false") == [personal["id"], unfinished["id"]]
    assert ids(is_done="true") == [finished["id"]]
    assert ids(category_id=first["id"]) == [finished["id"], unfinished["id"]]
    assert ids(is_done="false", category_id=first["id"]) == [unfinished["id"]]
    assert ids(is_done="true", category_id=second["id"]) == []
    assert ids(category_id=999999) == []


@pytest.mark.parametrize("path", ["/categories", "/assignees"])
def test_reference_names_are_unique_and_error_does_not_block_next_write(client, path):
    first = create(client, path, {"name": "同名"})
    duplicate = client.post(path, json={"name": "  同名  "})
    assert duplicate.status_code == 409
    second = create(client, path, {"name": "別名"})
    assert client.get(path).json() == [first, second]


@pytest.mark.parametrize("path", ["/categories", "/assignees"])
def test_reference_list_has_no_silent_100_item_limit(client, path):
    created = [create(client, path, {"name": f"名前{number}"}) for number in range(101)]
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == created


@pytest.mark.parametrize("payload", [
    {}, {"title": ""}, {"title": " \t\n "}, {"title": "あ" * 256},
    {"title": "タスク", "category_id": 0},
    {"title": "タスク", "assignee_id": -1},
    {"title": "タスク", "category_id": "invalid"},
    {"title": "タスク", "description": "あ" * 2001},
])
def test_invalid_task_is_rejected_without_inserting(client, payload):
    assert client.post("/tasks", json=payload).status_code == 422
    assert client.get("/tasks").json() == []


@pytest.mark.parametrize("path", ["/categories", "/assignees"])
@pytest.mark.parametrize("name", ["", " \t\n ", "あ" * 101, None])
def test_invalid_reference_names(client, path, name):
    assert client.post(path, json={"name": name}).status_code == 422
    assert client.get(path).json() == []


@pytest.mark.parametrize("field", ["category_id", "assignee_id"])
def test_missing_reference_does_not_create_or_modify_task(client, field):
    assert client.post("/tasks", json={"title": "作成失敗", field: 999999}).status_code == 404
    assert client.get("/tasks").json() == []

    task = create(client, "/tasks", {"title": "変更前"})
    path = f"/tasks/{task['id']}"
    response = client.put(path, json=full_update(task, title="変更失敗", **{field: 999999}))
    assert response.status_code == 404
    assert client.get(path).json() == task


@pytest.mark.parametrize("field", ["title", "description", "is_done", "category_id", "assignee_id"])
def test_put_requires_all_five_fields_and_preserves_previous_state(client, field):
    task = create(client, "/tasks", {"title": "変更前", "description": "保持する"})
    payload = full_update(task, title="変更後")
    del payload[field]
    path = f"/tasks/{task['id']}"
    assert client.put(path, json=payload).status_code == 422
    assert client.get(path).json() == task


def test_missing_task_is_404_for_read_update_delete(client):
    path = "/tasks/999999"
    payload = {"title": "存在しない", "description": None, "is_done": False,
               "category_id": None, "assignee_id": None}
    for response in [client.get(path), client.put(path, json=payload), client.delete(path)]:
        assert response.status_code == 404
        assert response.json() == {"detail": "Task not found"}


@pytest.mark.parametrize("path", ["/tasks/0", "/tasks/-1", "/tasks?category_id=0", "/tasks?is_done=invalid"])
def test_invalid_path_or_filter_returns_validation_error(client, path):
    assert client.get(path).status_code == 422


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_cors_allows_frontend_json_write_preflight(client, origin):
    response = client.options("/tasks/1", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "PUT",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "PUT" in response.headers["access-control-allow-methods"]
    assert client.get("/tasks", headers={"Origin": origin}).headers["access-control-allow-origin"] == origin


def test_cors_does_not_allow_unconfigured_origin(client):
    response = client.options("/tasks", headers={
        "Origin": "https://unconfigured.example",
        "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("path,payload", [
    ("/tasks", {"title": "保存失敗"}),
    ("/categories", {"name": "保存失敗"}),
    ("/assignees", {"name": "保存失敗"}),
])
def test_failed_commit_returns_generic_error_and_leaves_no_partial_row(client, db_sessions, monkeypatch, path, payload):
    original_commit = db_sessions.class_.commit
    attempts = 0

    def fail_once(db):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            # INSERT後のcommit失敗を模擬し、未確定の行が残らないことを検証する。
            db.flush()
            raise OperationalError("private SQL", {"password": "private password"}, RuntimeError("private DB error"))
        return original_commit(db)

    monkeypatch.setattr(db_sessions.class_, "commit", fail_once)
    response = client.post(path, json=payload, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Database operation failed"}
    assert "private" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert client.get(path).json() == []
    saved = create(client, path, payload)
    assert client.get(path).json() == [saved]
