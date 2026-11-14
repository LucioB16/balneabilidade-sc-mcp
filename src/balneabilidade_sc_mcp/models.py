"""Normalized IMA/SC models.

These models deliberately separate the official classification from the
freshness of the publication. A row can be official and outdated; it can be
excluded from the latest bulletin; it can be missing. None of those states is
silently converted to a current proper verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum


class Classification(StrEnum):
    PROPER = "proper"
    IMPROPER = "improper"
    INDETERMINATE = "indeterminate"
    UNKNOWN = "unknown"


class Freshness(StrEnum):
    CURRENT = "current"
    CARRIED_FORWARD = "carried_forward"
    EXCLUDED = "excluded"
    STALE = "stale"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"


class BeachStatus(StrEnum):
    PROPER = "proper"
    IMPROPER = "improper"
    MIXED = "mixed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class Qualifier(StrEnum):
    EXACT = "exact"
    BELOW = "below"
    ABOVE = "above"
    UNKNOWN = "unknown"


class Source(StrEnum):
    BULLETIN_PDF = "bulletin_pdf"
    CSV = "csv"
    ANALYSES = "analyses"
    CATALOG = "catalog"
    CACHE = "cache"


@dataclass(frozen=True)
class Ecoli:
    value: int | None
    qualifier: Qualifier
    raw: str

    @classmethod
    def from_parts(cls, value: int | None, qualifier: str, raw: str) -> Ecoli:
        try:
            parsed = Qualifier(qualifier)
        except ValueError:
            parsed = Qualifier.UNKNOWN
        return cls(value=value, qualifier=parsed, raw=raw)


@dataclass(frozen=True)
class CatalogPoint:
    point_id: str
    municipality: str
    beach: str
    point_name: str
    location: str
    latitude: float | None
    longitude: float | None
    hidden: bool = False


@dataclass(frozen=True)
class CatalogBeach:
    key: str
    municipality: str
    name: str
    points: tuple[CatalogPoint, ...]

    @property
    def point_count(self) -> int:
        return len(self.points)


@dataclass(frozen=True)
class Catalog:
    points: tuple[CatalogPoint, ...]
    fetched_at: datetime
    source_url: str
    stale: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def municipalities(self) -> tuple[str, ...]:
        return tuple(sorted({point.municipality for point in self.points}))

    @property
    def beaches(self) -> tuple[CatalogBeach, ...]:
        from .normalization import beach_key

        grouped: dict[str, list[CatalogPoint]] = {}
        for point in self.points:
            grouped.setdefault(beach_key(point.municipality, point.beach), []).append(point)
        result = [
            CatalogBeach(
                key=key,
                municipality=points[0].municipality,
                name=points[0].beach,
                points=tuple(sorted(points, key=lambda item: item.point_name)),
            )
            for key, points in grouped.items()
        ]
        return tuple(sorted(result, key=lambda beach: (beach.municipality, beach.name)))


@dataclass(frozen=True)
class BeachMatch:
    beach: CatalogBeach
    match_type: str


@dataclass(frozen=True)
class BulletinRow:
    municipality: str | None
    beach: str
    point_name: str
    sample_date: date
    classification: Classification
    raw_classification: str
    line_number: int | None = None


@dataclass(frozen=True)
class Bulletin:
    bulletin_date: date
    report_number: str | None
    collection_dates: tuple[date, ...]
    rows: tuple[BulletinRow, ...]
    excluded_point_numbers: frozenset[int]
    discarded_point_numbers: frozenset[int]
    exclusion_text: str
    source_url: str
    fetched_at: datetime
    stale: bool = False
    failed_pages: tuple[int, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CsvSample:
    municipality: str
    beach: str
    point_name: str
    sample_date: date
    sample_time: time | None
    classification: Classification
    raw_classification: str
    ecoli: Ecoli | None
    rain: str | None
    wind: str | None
    tide: str | None
    water_temp_c: float | None
    air_temp_c: float | None


@dataclass(frozen=True)
class CsvExport:
    municipality: str
    beach: str
    year: int
    samples: tuple[CsvSample, ...]
    no_data_points: tuple[str, ...]
    header: tuple[str, ...]
    fetched_at: datetime
    source_url: str
    stale: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysesSample:
    sample_date: date
    classification: Classification
    raw_classification: str
    rain: str | None
    result_raw: str | None
    ecoli: Ecoli | None
    water_temp_c: float | None


@dataclass(frozen=True)
class AnalysesResult:
    point_id: str
    samples: tuple[AnalysesSample, ...]
    fetched_at: datetime
    source_url: str
    stale: bool = False


@dataclass(frozen=True)
class PointStatus:
    point: CatalogPoint
    classification: Classification
    raw_classification: str | None
    sample_date: date | None
    bulletin_date: date | None
    sample_age_at_bulletin_days: int | None
    data_age_days: int | None
    freshness: Freshness
    ecoli: Ecoli | None
    rain: str | None
    water_temp_c: float | None
    source: Source
    value_source: Source | None
    source_url: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BeachSummary:
    status: BeachStatus
    points_total: int
    points_current: int
    points_improper: int
    points_stale: int
    points_excluded: int
    points_unknown: int
    has_improper: bool


@dataclass(frozen=True)
class BeachStatusResult:
    beach: CatalogBeach
    bulletin: Bulletin | None
    summary: BeachSummary
    points: tuple[PointStatus, ...]
    bulletin_unverified: bool
    latest_source: Source | None
    fetched_at: datetime
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoryRecord:
    point_id: str | None
    point_name: str
    sample_date: date
    sample_time: time | None
    classification: Classification
    raw_classification: str
    ecoli: Ecoli | None
    rain: str | None
    wind: str | None
    tide: str | None
    water_temp_c: float | None
    air_temp_c: float | None
    source: Source
    source_url: str


@dataclass(frozen=True)
class HistoryCoverage:
    years_requested: tuple[int, ...]
    years_with_data: tuple[int, ...]
    years_without_data: tuple[int, ...]


@dataclass(frozen=True)
class HistoryResult:
    beach: CatalogBeach
    from_date: date
    to_date: date
    records: tuple[HistoryRecord, ...]
    coverage: HistoryCoverage
    next_cursor: str | None
    unmatched_samples: int
    fetched_at: datetime
    warnings: tuple[str, ...] = field(default_factory=tuple)
