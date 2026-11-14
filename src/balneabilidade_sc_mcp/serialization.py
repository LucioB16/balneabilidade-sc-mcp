"""JSON-safe conversion for MCP tool responses."""

from __future__ import annotations

import base64
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Any

from .models import BeachStatusResult, Bulletin


def to_jsonable(value: Any) -> Any:
    """Convert provider dataclasses/enums/dates into JSON-compatible values."""

    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


def _bulletin_summary(bulletin: Bulletin | None) -> dict[str, Any] | None:
    if bulletin is None:
        return None
    return {
        "bulletin_date": bulletin.bulletin_date.isoformat(),
        "report_number": bulletin.report_number,
        "collection_dates": [item.isoformat() for item in bulletin.collection_dates],
        "source_url": bulletin.source_url,
        "fetched_at": bulletin.fetched_at.isoformat(),
        "stale": bulletin.stale,
        "failed_pages": list(bulletin.failed_pages),
        "excluded_point_numbers": sorted(bulletin.excluded_point_numbers),
        "discarded_point_numbers": sorted(bulletin.discarded_point_numbers),
        "warnings": list(bulletin.warnings),
    }


def _point_status(point_status: Any) -> dict[str, Any]:
    data = to_jsonable(point_status)
    point = data.pop("point", {})
    flattened = dict(point)
    flattened.update(data)
    return flattened


def status_to_dict(result: BeachStatusResult) -> dict[str, Any]:
    """Flatten point fields for the agent-facing status contract.

    The provider keeps the catalog point nested; the MCP contract exposes
    point_id, point_name, municipality and coordinates alongside the verdict.
    The full bulletin row list is intentionally not echoed.
    """

    return {
        "provider": "IMA/SC",
        "beach": {
            "beach_key": result.beach.key,
            "beach_name": result.beach.name,
            "municipality": result.beach.municipality,
            "point_count": result.beach.point_count,
        },
        "bulletin": _bulletin_summary(result.bulletin),
        "summary": to_jsonable(result.summary),
        "points": [_point_status(status) for status in result.points],
        "bulletin_unverified": result.bulletin_unverified,
        "latest_source": result.latest_source.value if result.latest_source else None,
        "vision_fallback": to_jsonable(result.vision_fallback),
        "fetched_at": result.fetched_at.isoformat(),
        "warnings": list(result.warnings),
    }
