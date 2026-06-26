"""Tests for optional external metrics service adapter."""

from __future__ import annotations

import json

import app.services.metrics_gateway as metrics_gateway_module
import pytest
from app.config import get_settings
from app.db.init_db import initialize_database
from app.tools.metrics_tool import calculate_gmv


class FakeResponse:
    """Minimal urlopen response context manager for metrics gateway tests."""

    status = 200

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Keep metrics backend env changes isolated."""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_external_metrics_service_payload(monkeypatch) -> None:
    """Metrics Tool should use an external payload when the gateway is configured."""

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        assert timeout == 2.0
        assert "/metrics/calculate_gmv" in request.full_url  # type: ignore[attr-defined]
        return FakeResponse(
            {
                "data": {
                    "product_id": "P1001",
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-30",
                    "gmv": 999.0,
                    "order_count": 9,
                    "sales_quantity": 9,
                }
            }
        )

    monkeypatch.setenv("METRICS_BACKEND", "http")
    monkeypatch.setenv("METRICS_SERVICE_URL", "https://metrics.example.test")
    monkeypatch.setenv("METRICS_SERVICE_TIMEOUT", "2")
    monkeypatch.setattr(metrics_gateway_module, "urlopen", fake_urlopen)
    get_settings.cache_clear()

    result = calculate_gmv("P1001", "2026-04-01", "2026-04-30")

    assert result["gmv"] == 999.0
    assert result["metrics_backend"] == "http"
    assert result["metrics_provider_status"]["status_code"] == 200


def test_external_metrics_service_falls_back_to_sqlite(monkeypatch) -> None:
    """External metrics failure should preserve the local SQLite demo path."""

    def failing_urlopen(request: object, timeout: float) -> FakeResponse:
        raise OSError("network unavailable")

    initialize_database()
    monkeypatch.setenv("METRICS_BACKEND", "http")
    monkeypatch.setenv("METRICS_SERVICE_URL", "https://metrics.example.test")
    monkeypatch.setenv("METRICS_SERVICE_FALLBACK_TO_SQLITE", "true")
    monkeypatch.setattr(metrics_gateway_module, "urlopen", failing_urlopen)
    get_settings.cache_clear()

    result = calculate_gmv("P1001", "2026-04-01", "2026-04-30")

    assert result["gmv"] > 0
    assert "metrics_backend" not in result
