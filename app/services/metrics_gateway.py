"""Gateway for optional external metrics service or warehouse adapters."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import get_settings

EXTERNAL_BACKENDS = {"http", "service", "warehouse", "data_warehouse"}


class MetricsGateway:
    """Fetch metrics from an external service with SQLite fallback by default.

    The project still uses local SQLite seed data for demos and CI. In a real
    deployment, setting METRICS_BACKEND=http and METRICS_SERVICE_URL lets the
    same tool surface read from a metrics API or warehouse proxy.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.backend = settings.metrics_backend.lower()
        self.service_url = (settings.metrics_service_url or "").rstrip("/")
        self.timeout = settings.metrics_service_timeout
        self.fallback_to_sqlite = settings.metrics_service_fallback_to_sqlite

    @property
    def enabled(self) -> bool:
        """Return whether an external metrics backend is configured."""

        return self.backend in EXTERNAL_BACKENDS and bool(self.service_url)

    def fetch_metric(self, metric_name: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Fetch one metric payload or return None when fallback should run."""

        if not self.enabled:
            return None

        query_string = urlencode(
            {key: value for key, value in params.items() if value is not None}
        )
        url = f"{self.service_url}/metrics/{metric_name}"
        if query_string:
            url = f"{url}?{query_string}"

        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                status_code = int(getattr(response, "status", getattr(response, "code", 0)) or 0)
                raw_text = response.read().decode("utf-8")
            parsed = json.loads(raw_text)
            payload = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed
            if not isinstance(payload, dict):
                raise RuntimeError("External metrics response must be a JSON object.")
            return {
                **payload,
                "metrics_backend": self.backend,
                "metrics_provider_status": {
                    "status_code": status_code,
                    "metric_name": metric_name,
                },
            }
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, RuntimeError):
            if self.fallback_to_sqlite:
                return None
            raise
