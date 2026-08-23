"""
tests/test_health.py — Phase 0: trivial smoke test for the /health endpoint.

Uses FastAPI's TestClient (backed by httpx) so no running server is needed.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    """GET /health must return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_status():
    """GET /health body must contain status='ok'."""
    response = client.get("/health")
    body = response.json()
    assert body.get("status") == "ok"


def test_health_returns_service_name():
    """GET /health body must identify the service."""
    response = client.get("/health")
    body = response.json()
    assert "service" in body
    assert body["service"] == "vitian-chatbot"


def test_health_returns_version():
    """GET /health body must include a version string."""
    response = client.get("/health")
    body = response.json()
    assert "version" in body
