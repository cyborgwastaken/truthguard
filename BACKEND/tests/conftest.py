import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import engine


@pytest.fixture()
def db():
    """A session inside a transaction that is rolled back after the test.

    Skips (does not fail) when Postgres is not running or the migration has not been applied.
    """
    try:
        connection = engine.connect()
    except OperationalError:
        pytest.skip("Postgres is not running. Start it: docker compose -f OPS/docker-compose.yml up -d")
    transaction = connection.begin()
    if "documents" not in inspect(connection).get_table_names():
        transaction.rollback()
        connection.close()
        pytest.skip("Tables missing. Run: cd BACKEND && alembic upgrade head")
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
