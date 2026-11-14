"""CSV history adapter.

The CSV has no point UUID or coordinates. Its join key is the name tuple
(municipality, beach, point), so parsing keeps the raw names and the provider
performs the conservative catalog join.
"""

from __future__ import annotations

import csv as csv_module
import io
from collections.abc import Callable
from datetime import datetime, timedelta

from .cache import Cache, utcnow
from .errors import ImaInvalidArgument, ImaSchemaError
from .http import ImaHttpClient
from .models import CsvExport, CsvSample, Ecoli
from .normalization import (
    classification_from_label,
    parse_br_date,
    parse_ecoli,
    parse_float,
    parse_time,
)

CSV_PATH = "/relatorio/exportarCSV"
CSV_URL = "https://balneabilidade.ima.sc.gov.br/relatorio/exportarCSV"
HISTORY_TTL_PAST = timedelta(days=30)
HISTORY_TTL_CURRENT = timedelta(hours=6)


def parse_csv(
    payload: bytes | str,
    *,
    municipality: str,
    beach: str,
    year: int,
    fetched_at: datetime,
    source_url: str = CSV_URL,
    stale: bool = False,
) -> CsvExport:
    text = payload.decode("utf-8-sig", errors="replace") if isinstance(payload, bytes) else payload
    reader = csv_module.reader(io.StringIO(text))
    try:
        header = tuple(cell.strip() for cell in next(reader))
    except StopIteration as exc:
        raise ImaSchemaError("CSV export was empty") from exc
    if len(header) < 13:
        raise ImaSchemaError(f"CSV export has {len(header)} columns, expected at least 13")
    warnings: list[str] = []
    samples: list[CsvSample] = []
    no_data_points: set[str] = set()
    for line_number, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) < 13:
            if any("sem registros" in cell.casefold() for cell in row):
                if len(row) > 2 and row[2].strip():
                    no_data_points.add(row[2].strip())
                continue
            warnings.append(f"short CSV row ignored at line {line_number}")
            continue
        try:
            sample_date = parse_br_date(row[4].strip())
        except (ValueError, IndexError):
            warnings.append(f"invalid date in CSV row {line_number}")
            continue
        raw_label = row[12].strip()
        if "sem registros" in raw_label.casefold():
            if row[2].strip():
                no_data_points.add(row[2].strip())
            continue
        try:
            sample_time = parse_time(row[5])
        except (ValueError, IndexError):
            sample_time = None
            warnings.append(f"invalid time in CSV row {line_number}")
        value, qualifier, raw_ecoli = parse_ecoli(row[11])
        samples.append(
            CsvSample(
                municipality=row[0].strip() or municipality,
                beach=row[1].strip() or beach,
                point_name=row[2].strip(),
                sample_date=sample_date,
                sample_time=sample_time,
                classification=classification_from_label(raw_label),
                raw_classification=raw_label,
                ecoli=Ecoli.from_parts(value, qualifier, raw_ecoli),
                rain=_clean(row[8]),
                wind=_clean(row[6]),
                tide=_clean(row[7]),
                water_temp_c=parse_float(row[9]),
                air_temp_c=parse_float(row[10]),
                location=_clean(row[3]),
            )
        )
    return CsvExport(
        municipality=municipality,
        beach=beach,
        year=year,
        samples=tuple(samples),
        no_data_points=tuple(sorted(no_data_points)),
        header=header,
        fetched_at=fetched_at,
        source_url=source_url,
        stale=stale,
        warnings=tuple(warnings),
    )


def _clean(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


class CsvHistoryRepository:
    def __init__(
        self,
        http: ImaHttpClient,
        cache: Cache,
        *,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._http = http
        self._cache = cache
        self._clock = clock

    async def fetch(self, municipality: str, beach: str, year: int) -> CsvExport:
        if not municipality.strip() or not beach.strip():
            raise ImaInvalidArgument("municipality and beach are required")
        if not 2003 <= year <= self._clock().year + 1:
            raise ImaInvalidArgument(f"year {year} is outside the supported IMA range")
        cache_key = f"csv:{municipality}|{beach}|{year}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return parse_csv(
                cached.data,
                municipality=municipality,
                beach=beach,
                year=year,
                fetched_at=cached.fetched_at,
                stale=False,
            )
        try:
            response = await self._http.post_form(
                CSV_PATH,
                {"municipioID": municipality, "localID": beach, "ano": str(year)},
            )
        except Exception:
            stale = await self._cache.get(cache_key, allow_stale=True)
            if stale is None:
                raise
            export = parse_csv(
                stale.data,
                municipality=municipality,
                beach=beach,
                year=year,
                fetched_at=stale.fetched_at,
                stale=True,
            )
            return _with_warning(export, "CSV refresh failed; serving stale cached export")
        if "csv" not in response.content_type.lower() and not response.content.startswith(b"\xef\xbb\xbf"):
            raise ImaSchemaError("CSV export did not return CSV")
        export = parse_csv(
            response.content,
            municipality=municipality,
            beach=beach,
            year=year,
            fetched_at=response.fetched_at,
            stale=False,
        )
        ttl = HISTORY_TTL_CURRENT if year >= self._clock().year else HISTORY_TTL_PAST
        await self._cache.set(cache_key, response.content, response.content_type, ttl)
        return export


def _with_warning(export: CsvExport, warning: str) -> CsvExport:
    return CsvExport(
        municipality=export.municipality,
        beach=export.beach,
        year=export.year,
        samples=export.samples,
        no_data_points=export.no_data_points,
        header=export.header,
        fetched_at=export.fetched_at,
        source_url=export.source_url,
        stale=export.stale,
        warnings=(*export.warnings, warning),
    )
