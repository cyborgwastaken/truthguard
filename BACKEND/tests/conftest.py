import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import engine


@pytest.fixture()
def db():
    """A session on an empty database, inside a transaction that is rolled back after the test.

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
    # Start every test from an empty database. This happens inside the transaction that is rolled
    # back below, so documents loaded for development (OPS/load_fixtures.py) are not touched.
    # Answers go first: answer_citations references chunks without ON DELETE CASCADE.
    connection.execute(text("DELETE FROM answers"))
    connection.execute(text("DELETE FROM documents"))
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    """FastAPI test client whose requests run on the rolled-back test session."""
    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.main import app

    app.dependency_overrides[get_session] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
