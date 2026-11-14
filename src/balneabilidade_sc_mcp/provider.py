"""Reconciliation layer: official bulletin + CSV values + per-point analyses.

The provider never turns the map's undated CONDICAO into a current verdict.
It joins the latest bulletin to the catalog by municipality + beach + point,
honors the bulletin's exclusion/carry-forward context, and uses CSV only for
dated history, lab values and a clearly labelled fallback.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .analyses import ANALYSES_URL, AnalysesRepository
from .bulletin import BulletinRepository
from .cache import Cache, FileCache, utcnow
from .catalog import (
    CatalogRepository,
    find_point,
    resolve_beach,
)
from .catalog import search_beaches as search_catalog
from .errors import (
    ImaError,
    ImaInvalidArgument,
    ImaNoData,
    ImaProviderUnavailable,
)
from .history import CsvHistoryRepository
from .http import ImaHttpClient
from .models import (
    AnalysesSample,
    BeachMatch,
    BeachStatus,
    BeachStatusResult,
    BeachSummary,
    Bulletin,
    BulletinRow,
    Catalog,
    CatalogBeach,
    CatalogPoint,
    Classification,
    CsvExport,
    CsvSample,
    Freshness,
    HistoryCoverage,
    HistoryRecord,
    HistoryResult,
    PointStatus,
    Source,
)
from .normalization import fold, is_in_season, point_number

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
IN_SEASON_WINDOW_DAYS = 10
OFF_SEASON_WINDOW_DAYS = 40
MAX_HISTORY_YEARS = 10
DEFAULT_HISTORY_LIMIT = 50
MAX_HISTORY_LIMIT = 200


class ImaProvider:
    def __init__(
        self,
        *,
        http: ImaHttpClient | None = None,
        cache: Cache | None = None,
        catalog_repository: CatalogRepository | None = None,
        bulletin_repository: BulletinRepository | None = None,
        history_repository: CsvHistoryRepository | None = None,
        analyses_repository: AnalysesRepository | None = None,
        clock: Callable[[], datetime] = utcnow,
        today: Callable[[], date] | None = None,
    ) -> None:
        self._owns_http = http is None
        self._http = http or ImaHttpClient()
        self._cache = cache or FileCache(Path(".cache/balneabilidade"))
        self._catalog = catalog_repository or CatalogRepository(self._http, self._cache)
        self._bulletin = bulletin_repository or BulletinRepository(self._http, self._cache)
        self._history = history_repository or CsvHistoryRepository(self._http, self._cache)
        self._analyses = analyses_repository or AnalysesRepository(self._http, self._cache)
        self._clock = clock
        self._today = today or (lambda: datetime.now(SAO_PAULO).date())

    async def __aenter__(self) -> ImaProvider:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def search_beaches(
        self,
        query: str,
        *,
        municipality: str | None = None,
        limit: int = 10,
    ) -> tuple[BeachMatch, ...]:
        catalog = await self._catalog.load()
        return search_catalog(catalog, query, municipality=municipality, limit=limit)

    async def get_sampling_points(
        self,
        beach: str,
        *,
        municipality: str | None = None,
        include_hidden: bool = False,
    ) -> CatalogBeach:
        catalog = await self._catalog.load()
        resolved = resolve_beach(catalog, beach, municipality=municipality)
        points = resolved.points if include_hidden else tuple(p for p in resolved.points if not p.hidden)
        if not points:
            raise ImaNoData(f"no visible sampling points for {resolved.name!r}")
        return CatalogBeach(
            key=resolved.key,
            municipality=resolved.municipality,
            name=resolved.name,
            points=points,
        )

    async def get_bathing_status(
        self,
        beach: str,
        *,
        municipality: str | None = None,
        point_id: str | None = None,
    ) -> BeachStatusResult:
        catalog = await self._catalog.load()
        resolved = resolve_beach(catalog, beach, municipality=municipality)
        points = self._select_points(resolved, point_id)
        warnings: list[str] = list(catalog.warnings)
        bulletin: Bulletin | None = None
        try:
            bulletin = await self._bulletin.fetch(known_municipalities=catalog.municipalities)
        except ImaError as exc:
            warnings.append(f"latest bulletin unavailable: {exc}")
        if bulletin is not None:
            if bulletin.stale:
                warnings.append("latest bulletin was served from stale cache")
            warnings.extend(bulletin.warnings)
            statuses = await self._statuses_from_bulletin(points, catalog, bulletin, warnings)
            latest_source: Source | None = Source.BULLETIN_PDF
            bulletin_unverified = False
        else:
            statuses = await self._statuses_without_bulletin(points, catalog, warnings)
            latest_source = _first_source(statuses)
            bulletin_unverified = True
            warnings.append(
                "no verified bulletin; status is a dated fallback and must not be presented as current"
            )
        summary = self._summarize(statuses)
        return BeachStatusResult(
            beach=resolved,
            bulletin=bulletin,
            summary=summary,
            points=tuple(statuses),
            bulletin_unverified=bulletin_unverified,
            latest_source=latest_source,
            fetched_at=self._clock(),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    async def get_bathing_history(
        self,
        beach: str,
        *,
        municipality: str | None = None,
        point_id: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = DEFAULT_HISTORY_LIMIT,
        cursor: str | None = None,
    ) -> HistoryResult:
        if not 1 <= limit <= MAX_HISTORY_LIMIT:
            raise ImaInvalidArgument(f"limit must be between 1 and {MAX_HISTORY_LIMIT}")
        today = self._today()
        start = from_date or date(today.year, 1, 1)
        end = to_date or today
        if start > end:
            raise ImaInvalidArgument("from_date must be before or equal to to_date")
        if start < date(2003, 1, 1):
            raise ImaInvalidArgument("IMA history starts in 2003")
        if end > today:
            raise ImaInvalidArgument("to_date must not be in the future")
        years = tuple(range(start.year, end.year + 1))
        if len(years) > MAX_HISTORY_YEARS:
            raise ImaInvalidArgument(f"date range spans more than {MAX_HISTORY_YEARS} years")

        catalog = await self._catalog.load()
        resolved = resolve_beach(catalog, beach, municipality=municipality)
        selected = self._select_points(resolved, point_id)
        selected_by_name = {fold(point.point_name): point for point in selected}
        beach_names = {fold(point.point_name) for point in resolved.points}
        warnings: list[str] = list(catalog.warnings)
        records: list[HistoryRecord] = []
        years_with_data: list[int] = []
        years_without_data: list[int] = []
        unmatched = 0
        successful_exports = 0
        errors: list[ImaError] = []
        for year in years:
            try:
                export = await self._history.fetch(resolved.municipality, resolved.name, year)
            except ImaError as exc:
                errors.append(exc)
                warnings.append(f"CSV unavailable for {year}: {exc}")
                continue
            successful_exports += 1
            if export.stale:
                warnings.append(f"CSV for {year} was served from stale cache")
            warnings.extend(export.warnings)
            year_records: list[HistoryRecord] = []
            for sample in export.samples:
                if sample.sample_date < start or sample.sample_date > end:
                    continue
                folded_name = fold(sample.point_name)
                point = selected_by_name.get(folded_name)
                if point is None:
                    if folded_name not in beach_names:
                        unmatched += 1
                    continue
                year_records.append(self._history_record(point, sample, export.source_url))
            if year_records:
                years_with_data.append(year)
                records.extend(year_records)
            else:
                years_without_data.append(year)
        if successful_exports == 0 and errors:
            raise ImaProviderUnavailable(f"no CSV history could be fetched: {errors[0]}") from errors[0]
        records.sort(key=lambda record: (record.sample_date, record.point_name), reverse=True)
        offset = _parse_cursor(cursor)
        page = records[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(records) else None
        return HistoryResult(
            beach=resolved,
            from_date=start,
            to_date=end,
            records=tuple(page),
            coverage=HistoryCoverage(
                years_requested=years,
                years_with_data=tuple(years_with_data),
                years_without_data=tuple(years_without_data),
            ),
            next_cursor=next_cursor,
            unmatched_samples=unmatched,
            fetched_at=self._clock(),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _select_points(self, beach: CatalogBeach, point_id: str | None) -> tuple[CatalogPoint, ...]:
        if point_id is None:
            points = tuple(point for point in beach.points if not point.hidden)
            if not points:
                raise ImaNoData(f"no visible sampling points for {beach.name!r}")
            return points
        return (find_point(beach, point_id),)

    async def _statuses_from_bulletin(
        self,
        points: Sequence[CatalogPoint],
        catalog: Catalog,
        bulletin: Bulletin,
        warnings: list[str],
    ) -> list[PointStatus]:
        by_three: dict[tuple[str, str, str], BulletinRow] = {}
        by_two: dict[tuple[str, str], list[BulletinRow]] = {}
        for row in bulletin.rows:
            two = (fold(row.beach), fold(row.point_name))
            by_two.setdefault(two, []).append(row)
            if row.municipality:
                three = (fold(row.municipality), fold(row.beach), fold(row.point_name))
                if three in by_three:
                    warnings.append(f"duplicate bulletin row for {row.beach} / {row.point_name}")
                by_three[three] = row

        mentioned_municipalities = {
            fold(name) for name in catalog.municipalities if fold(name) in fold(bulletin.exclusion_text)
        }
        statuses: list[PointStatus] = []
        for point in points:
            matched, issue = _find_row(point, by_three, by_two)
            if issue:
                warnings.append(f"{point.beach} / {point.point_name}: {issue}")
            if matched is None:
                warnings.append(f"{point.beach} / {point.point_name}: missing from latest bulletin")
                statuses.append(
                    self._unknown_status(
                        point,
                        bulletin_date=bulletin.bulletin_date,
                        source_url=bulletin.source_url,
                        warning="point missing from the latest bulletin",
                    )
                )
                continue
            excluded = _is_excluded(point, bulletin, mentioned_municipalities)
            classification = matched.classification
            freshness = Freshness.CURRENT
            point_warnings: list[str] = []
            if excluded:
                classification = Classification.UNKNOWN
                freshness = Freshness.EXCLUDED
                point_warnings.append("point is explicitly excluded/carried as invalid in this bulletin")
            else:
                freshness, _age, reason = self._row_freshness(matched, bulletin)
                if reason:
                    point_warnings.append(reason)
            sample_age = (bulletin.bulletin_date - matched.sample_date).days
            statuses.append(
                PointStatus(
                    point=point,
                    classification=classification,
                    raw_classification=matched.raw_classification,
                    sample_date=matched.sample_date,
                    bulletin_date=bulletin.bulletin_date,
                    sample_age_at_bulletin_days=sample_age,
                    data_age_days=(self._today() - row.sample_date).days,
                    freshness=freshness,
                    ecoli=None,
                    rain=None,
                    water_temp_c=None,
                    source=Source.BULLETIN_PDF,
                    value_source=None,
                    source_url=bulletin.source_url,
                    warnings=tuple(point_warnings),
                )
            )
        enriched, enrichment_warnings = await self._enrich_with_csv(statuses, warnings)
        warnings.extend(enrichment_warnings)
        return enriched

    def _row_freshness(
        self, row: BulletinRow, bulletin: Bulletin
    ) -> tuple[Freshness, int, str]:
        age = (bulletin.bulletin_date - row.sample_date).days
        if age < 0:
            return Freshness.STALE, age, "sample date is after the bulletin date"
        window = IN_SEASON_WINDOW_DAYS if is_in_season(bulletin.bulletin_date) else OFF_SEASON_WINDOW_DAYS
        if (
            is_in_season(bulletin.bulletin_date)
            and bulletin.collection_dates
            and row.sample_date not in bulletin.collection_dates
        ):
            return (
                Freshness.CARRIED_FORWARD,
                age,
                "sample date is outside the bulletin's stated collection dates",
            )
        if age > window:
            return (
                Freshness.CARRIED_FORWARD,
                age,
                f"sample is {age} days older than the bulletin (window {window} days)",
            )
        return Freshness.CURRENT, age, ""

    async def _enrich_with_csv(
        self, statuses: Sequence[PointStatus], warnings: list[str]
    ) -> tuple[list[PointStatus], list[str]]:
        extra_warnings: list[str] = []
        groups: dict[tuple[str, str, int], list[int]] = {}
        for index, status in enumerate(statuses):
            if status.sample_date is None or status.classification == Classification.UNKNOWN:
                continue
            key = (status.point.municipality, status.point.beach, status.sample_date.year)
            groups.setdefault(key, []).append(index)
        enriched = list(statuses)
        for (municipality, beach, year), indices in groups.items():
            try:
                export = await self._history.fetch(municipality, beach, year)
            except ImaError as exc:
                extra_warnings.append(f"CSV lab values unavailable for {beach} {year}: {exc}")
                continue
            if export.stale:
                extra_warnings.append(f"CSV lab values for {beach} {year} came from stale cache")
            samples = {
                (fold(sample.point_name), sample.sample_date): sample for sample in export.samples
            }
            for index in indices:
                status = enriched[index]
                if status.sample_date is None:
                    continue
                sample = samples.get((fold(status.point.point_name), status.sample_date))
                if sample is None:
                    continue
                status_warnings = list(status.warnings)
                if (
                    sample.classification != Classification.UNKNOWN
                    and status.classification != Classification.UNKNOWN
                    and sample.classification != status.classification
                ):
                    status_warnings.append(
                        "CSV classification differs from the bulletin; bulletin verdict kept"
                    )
                enriched[index] = replace(
                    status,
                    ecoli=sample.ecoli,
                    rain=sample.rain,
                    water_temp_c=sample.water_temp_c,
                    value_source=Source.CSV,
                    warnings=tuple(status_warnings),
                )
        return enriched, extra_warnings

    async def _statuses_without_bulletin(
        self,
        points: Sequence[CatalogPoint],
        catalog: Catalog,
        warnings: list[str],
    ) -> list[PointStatus]:
        bulletin_date: date | None
        try:
            bulletin_date = await self._bulletin.latest_date()
        except ImaError as exc:
            bulletin_date = None
            warnings.append(f"bulletin index unavailable too: {exc}")
        statuses: list[PointStatus] = []
        for point in points:
            sample, export = await self._latest_csv_sample(point, warnings)
            if sample is not None:
                freshness, point_warning, age = self._fallback_freshness(sample.sample_date, bulletin_date)
                statuses.append(
                    PointStatus(
                        point=point,
                        classification=sample.classification,
                        raw_classification=sample.raw_classification,
                        sample_date=sample.sample_date,
                        bulletin_date=bulletin_date,
                        sample_age_at_bulletin_days=age,
                        data_age_days=(self._today() - sample.sample_date).days,
                        freshness=freshness,
                        ecoli=sample.ecoli,
                        rain=sample.rain,
                        water_temp_c=sample.water_temp_c,
                        source=Source.CSV,
                        value_source=Source.CSV,
                        source_url=export.source_url if export else catalog.source_url,
                        warnings=(point_warning,) if point_warning else (),
                    )
                )
                continue
            analyses = await self._latest_analyses(point, warnings)
            if analyses is not None:
                freshness, point_warning, age = self._fallback_freshness(
                    analyses.sample_date, bulletin_date
                )
                statuses.append(
                    PointStatus(
                        point=point,
                        classification=analyses.classification,
                        raw_classification=analyses.raw_classification,
                        sample_date=analyses.sample_date,
                        bulletin_date=bulletin_date,
                        sample_age_at_bulletin_days=age,
                        data_age_days=(self._today() - analyses.sample_date).days,
                        freshness=freshness,
                        ecoli=analyses.ecoli,
                        rain=analyses.rain,
                        water_temp_c=analyses.water_temp_c,
                        source=Source.ANALYSES,
                        value_source=Source.ANALYSES,
                        source_url=ANALYSES_URL,
                        warnings=(point_warning,) if point_warning else (),
                    )
                )
                continue
            statuses.append(
                self._unknown_status(
                    point,
                    bulletin_date=bulletin_date,
                    source_url=catalog.source_url,
                    warning="no dated CSV or analyses result available",
                )
            )
        return statuses

    def _fallback_freshness(
        self, sample_date: date, bulletin_date: date | None
    ) -> tuple[Freshness, str, int | None]:
        if sample_date > self._today():
            return Freshness.UNKNOWN, "sample date is in the future", None
        if bulletin_date is None:
            return Freshness.UNVERIFIED, "no bulletin date; dated fallback is unverified", None
        age = (bulletin_date - sample_date).days
        window = IN_SEASON_WINDOW_DAYS if is_in_season(bulletin_date) else OFF_SEASON_WINDOW_DAYS
        if age > window:
            return (
                Freshness.STALE,
                f"fallback sample is {age} days older than the bulletin (window {window} days)",
                age,
            )
        return Freshness.UNVERIFIED, "fallback sample is dated but not verified against a bulletin", age

    async def _latest_csv_sample(
        self, point: CatalogPoint, warnings: list[str]
    ) -> tuple[CsvSample | None, CsvExport | None]:
        today = self._today()
        for year in (today.year, today.year - 1):
            try:
                export = await self._history.fetch(point.municipality, point.beach, year)
            except ImaError as exc:
                warnings.append(f"CSV fallback unavailable for {point.beach} {year}: {exc}")
                continue
            if export.stale:
                warnings.append(f"CSV fallback for {point.beach} {year} came from stale cache")
            candidates = [
                sample
                for sample in export.samples
                if fold(sample.point_name) == fold(point.point_name)
            ]
            if candidates:
                return max(candidates, key=lambda sample: sample.sample_date), export
        return None, None

    async def _latest_analyses(
        self, point: CatalogPoint, warnings: list[str]
    ) -> AnalysesSample | None:
        try:
            result = await self._analyses.fetch(point.point_id)
        except ImaError as exc:
            warnings.append(f"analyses fallback unavailable for {point.point_name}: {exc}")
            return None
        return result.samples[0] if result.samples else None

    def _unknown_status(
        self, point: CatalogPoint, *, bulletin_date: date | None, source_url: str, warning: str
    ) -> PointStatus:
        return PointStatus(
            point=point,
            classification=Classification.UNKNOWN,
            raw_classification=None,
            sample_date=None,
            bulletin_date=bulletin_date,
            sample_age_at_bulletin_days=None,
            data_age_days=None,
            freshness=Freshness.UNKNOWN,
            ecoli=None,
            rain=None,
            water_temp_c=None,
            source=Source.CATALOG,
            value_source=None,
            source_url=source_url,
            warnings=(warning,),
        )

    def _summarize(self, statuses: Sequence[PointStatus]) -> BeachSummary:
        total = len(statuses)
        current = sum(status.freshness == Freshness.CURRENT for status in statuses)
        improper = sum(status.classification == Classification.IMPROPER for status in statuses)
        stale = sum(
            status.freshness in (Freshness.CARRIED_FORWARD, Freshness.STALE) for status in statuses
        )
        excluded = sum(status.freshness == Freshness.EXCLUDED for status in statuses)
        unknown = sum(status.freshness == Freshness.UNKNOWN for status in statuses)
        proper = sum(status.classification == Classification.PROPER for status in statuses)
        if not statuses:
            status = BeachStatus.UNKNOWN
        elif improper:
            status = BeachStatus.MIXED if proper else BeachStatus.IMPROPER
        elif proper and current == total and all(
            item.classification == Classification.PROPER for item in statuses
        ):
            status = BeachStatus.PROPER
        elif proper:
            status = BeachStatus.PARTIAL
        else:
            status = BeachStatus.UNKNOWN
        return BeachSummary(
            status=status,
            points_total=total,
            points_current=current,
            points_improper=improper,
            points_stale=stale,
            points_excluded=excluded,
            points_unknown=unknown,
            has_improper=improper > 0,
        )

    def _history_record(
        self, point: CatalogPoint, sample: CsvSample, source_url: str
    ) -> HistoryRecord:
        return HistoryRecord(
            point_id=point.point_id,
            point_name=point.point_name,
            sample_date=sample.sample_date,
            sample_time=sample.sample_time,
            classification=sample.classification,
            raw_classification=sample.raw_classification,
            ecoli=sample.ecoli,
            rain=sample.rain,
            wind=sample.wind,
            tide=sample.tide,
            water_temp_c=sample.water_temp_c,
            air_temp_c=sample.air_temp_c,
            source=Source.CSV,
            source_url=source_url,
        )


def _find_row(
    point: CatalogPoint,
    by_three: dict[tuple[str, str, str], BulletinRow],
    by_two: dict[tuple[str, str], list[BulletinRow]],
) -> tuple[BulletinRow | None, str]:
    three = (fold(point.municipality), fold(point.beach), fold(point.point_name))
    row = by_three.get(three)
    if row is not None:
        return row, ""
    candidates = by_two.get((fold(point.beach), fold(point.point_name)), [])
    if len(candidates) == 1:
        return candidates[0], "joined by beach+point because municipality heading was unavailable"
    if len(candidates) > 1:
        return None, "ambiguous beach+point match across municipalities"
    return None, "no matching bulletin row"


def _is_excluded(
    point: CatalogPoint, bulletin: Bulletin, mentioned_municipalities: set[str]
) -> bool:
    number = point_number(point.point_name)
    if number is None or number not in bulletin.discarded_point_numbers:
        return False
    if not mentioned_municipalities:
        return True
    return fold(point.municipality) in mentioned_municipalities


def _first_source(statuses: Sequence[PointStatus]) -> Source | None:
    for status in statuses:
        if status.source != Source.CATALOG:
            return status.source
    return None


def _parse_cursor(cursor: str | None) -> int:
    if cursor is None or not cursor.strip():
        return 0
    try:
        value = int(cursor)
    except ValueError as exc:
        raise ImaInvalidArgument("cursor must be a non-negative integer offset") from exc
    if value < 0:
        raise ImaInvalidArgument("cursor must be a non-negative integer offset")
    return value
