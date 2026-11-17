from app.core.database import get_engine


def test_sqlite_foreign_keys_are_enabled(client):
    with get_engine().connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1


def test_sqlite_uses_wal_for_concurrent_job_progress(client):
    with get_engine().connect() as connection:
        assert connection.exec_driver_sql('PRAGMA journal_mode').scalar().lower() == 'wal'
