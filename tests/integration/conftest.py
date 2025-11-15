"""Pytest fixtures for integration tests."""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.app.models import Base
from src.app.main import app


@pytest.fixture(scope="function")
def db():
    """Create an in-memory SQLite database for integration testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with a test database session."""
    def override_get_db():
        yield db

    from src.app import database
    app.dependency_overrides[database.get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def set_webhook_secret(monkeypatch):
    """Set WEBHOOK_SECRET for webhook tests."""
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret-123")
