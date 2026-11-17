from app.core.database import engine

def test_sqlite_foreign_keys_are_enabled():
    with engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
