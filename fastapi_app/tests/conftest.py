"""実際のルーターを、一時 SQLite DB に接続して検証する。

MySQL のエンジンは接続前に差し替えるため、利用者の test_db は操作しない。
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# .env の用意や MySQL の起動なしでアプリを import できる設定。
# この設定の MySQL に接続することはない。
with patch.dict(os.environ, {
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "1",
    "DB_NAME": "unused_test_config",
    "DB_USER": "unused_test_config",
    "DB_PASSWORD": "unused_test_config",
    "CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
}):
    from task_app import dependencies, main


@pytest.fixture
def db_sessions(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(main, "engine", engine)
    # get_db 本体はそのまま使い、実際の rollback / close も検証する。
    monkeypatch.setattr(dependencies, "SessionLocal", sessions)
    try:
        yield sessions
    finally:
        engine.dispose()


@pytest.fixture
def client(db_sessions):
    # lifespan のテーブル作成も、差し替えた一時 DB に対して実行する。
    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client
