from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests


class PrometheusClient:
    def __init__(self, base_url: str, timeout_seconds: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step_seconds: int,
    ) -> pd.Series:
        response = self.session.get(
            f"{self.base_url}/api/v1/query_range",
            params={
                "query": query,
                "start": start.astimezone(timezone.utc).timestamp(),
                "end": end.astimezone(timezone.utc).timestamp(),
                "step": step_seconds,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            raise RuntimeError(f"Prometheus query failed: {payload}")
        results = payload.get("data", {}).get("result", [])
        if not results:
            return pd.Series(dtype="float64")

        combined: pd.Series | None = None
        for result in results:
            values = result.get("values", [])
            series = pd.Series(
                [float(value) for _, value in values],
                index=pd.to_datetime([timestamp for timestamp, _ in values], unit="s", utc=True),
                dtype="float64",
            )
            combined = series if combined is None else combined.add(series, fill_value=0.0)
        assert combined is not None
        return combined.sort_index()

