"""Latest official bulletin: index discovery, PDF extraction and parsing.

The PDF is the only source that carries a publication date, per-point sample
dates and the bulletin's own exclusion/carry-forward context. Parsing is
defensive: a malformed page (observed on page 19 of the current PDF) must not
discard the point table, and a wrapped heading must not move a verdict to the
next point.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Protocol

from pypdf import PdfReader

from .cache import Cache, utcnow
from .errors import ImaNotFound, ImaSchemaError
from .http import ImaHttpClient
from .models import Bulletin, BulletinRow
from .normalization import (
    classification_from_label,
    fold,
    parse_br_date,
    parse_collection_dates,
)

BASE_URL = "https://balneabilidade.ima.sc.gov.br"
INDEX_PATH = "/"
PDF_PATH = "/relatorio/downloadPDF/{date}"
INDEX_CACHE_KEY = "bulletin:index"
INDEX_TTL = timedelta(hours=1)
PDF_TTL = timedelta(days=3650)

BULLETIN_LINK = re.compile(r"/relatorio/downloadPDF/(\d{4}-\d{2}-\d{2})")
REPORT_NUMBER = re.compile(r"RELAT[ÓO]RIO\s+N[º°o]?\s*(\d+)", re.IGNORECASE)
BULLETIN_DATE = re.compile(r"DATA:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
HEADING = re.compile(r"^(?P<beach>.+?)\s*\(\s*(?P<point>Ponto\s+\d+)\s*\)\s*(?P<rest>.*)$")
DATE_VERDICT = re.compile(r"(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<verdict>[^\d\s]+)")
POINT_NUMBERS = re.compile(r"Ponto[s]?\s+((?:\d{1,3})(?:\s*(?:,|e)\s*\d{1,3})*)", re.IGNORECASE)


@dataclass(frozen=True)
class BulletinIndex:
    dates: tuple[date, ...]
    fetched_at: datetime
    source_url: str
    stale: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def latest(self) -> date:
        if not self.dates:
            raise ImaNotFound("bulletin index contains no dates")
        return self.dates[-1]


@dataclass(frozen=True)
class ExtractedPdf:
    pages: tuple[str, ...]
    failed_pages: tuple[int, ...] = ()

    @property
    def text(self) -> str:
        return "\n".join(self.pages)


class PdfExtractor(Protocol):
    def extract(self, data: bytes) -> ExtractedPdf: ...


class PypdfExtractor:
    def extract(self, data: bytes) -> ExtractedPdf:
        reader = PdfReader(BytesIO(data))
        pages: list[str] = []
        failed: list[int] = []
        for index, page in enumerate(reader.pages, start=1):
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
                failed.append(index)
        return ExtractedPdf(pages=tuple(pages), failed_pages=tuple(failed))


def parse_index(html: str, *, fetched_at: datetime, source_url: str = BASE_URL + "/") -> BulletinIndex:
    dates = sorted({parse_br_date_iso(value) for value in BULLETIN_LINK.findall(html)})
    if not dates:
        raise ImaSchemaError("portal index contains no bulletin links")
    return BulletinIndex(dates=tuple(dates), fetched_at=fetched_at, source_url=source_url)


def parse_br_date_iso(value: str) -> date:
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def _reflow_lines(text: str) -> list[str]:
    raw = [line.strip() for line in text.splitlines()]
    lines: list[str] = []
    index = 0
    while index < len(raw):
        line = raw[index]
        if index + 1 < len(raw):
            following = raw[index + 1].strip()
            if re.search(r"\(Ponto\s*$", line, re.IGNORECASE) and re.match(r"^\d+\)", following):
                lines.append(f"{line} {following}")
                index += 2
                continue
            if re.search(r"\(Ponto\s+\d+\s*$", line, re.IGNORECASE) and following == ")":
                lines.append(f"{line})")
                index += 2
                continue
        lines.append(line)
        index += 1
    return lines


def parse_bulletin_text(
    text: str,
    *,
    source_url: str,
    fetched_at: datetime,
    bulletin_date_hint: date | None = None,
    known_municipalities: Sequence[str] = (),
    failed_pages: Sequence[int] = (),
    stale: bool = False,
) -> Bulletin:
    warnings: list[str] = []
    if failed_pages:
        warnings.append(f"PDF pages failed to extract: {', '.join(str(page) for page in failed_pages)}")

    report_match = REPORT_NUMBER.search(text)
    report_number = report_match.group(1) if report_match else None
    date_match = BULLETIN_DATE.search(text)
    if date_match:
        bulletin_date = parse_br_date(date_match.group(1))
        if bulletin_date_hint is not None and bulletin_date != bulletin_date_hint:
            warnings.append(
                f"bulletin date {bulletin_date} differs from link date {bulletin_date_hint}"
            )
    elif bulletin_date_hint is not None:
        bulletin_date = bulletin_date_hint
        warnings.append("bulletin date missing from PDF; using link date")
    else:
        raise ImaSchemaError("bulletin PDF has no DATA field and no date hint")

    collection_dates = parse_collection_dates(text)
    if not collection_dates:
        warnings.append("bulletin collection dates were not parsed")

    municipality_lookup = {fold(name): name for name in known_municipalities}
    current_municipality: str | None = None
    rows: list[BulletinRow] = []
    seen: set[tuple[str | None, str, str, date, str]] = set()
    unparsed_headings = 0
    lines = _reflow_lines(text)
    for line_number, line in enumerate(lines, start=1):
        if line and fold(line) in municipality_lookup:
            current_municipality = municipality_lookup[fold(line)]
            continue
        heading = HEADING.match(line)
        if not heading:
            continue
        beach = heading.group("beach").strip()
        point_name = " ".join(heading.group("point").split())
        if not beach or beach.startswith("*"):
            continue
        match = DATE_VERDICT.search(heading.group("rest"))
        if match is None:
            for offset in range(1, 8):
                if line_number - 1 + offset >= len(lines):
                    break
                candidate = lines[line_number - 1 + offset]
                if HEADING.match(candidate):
                    break
                match = DATE_VERDICT.search(candidate)
                if match is not None:
                    break
        if match is None:
            unparsed_headings += 1
            continue
        try:
            sample_date = parse_br_date(match.group("date"))
        except ValueError:
            unparsed_headings += 1
            continue
        raw_label = match.group("verdict").strip()
        key = (current_municipality, fold(beach), fold(point_name), sample_date, fold(raw_label))
        if key in seen:
            warnings.append(f"duplicate bulletin row ignored: {beach} / {point_name} / {sample_date}")
            continue
        seen.add(key)
        rows.append(
            BulletinRow(
                municipality=current_municipality,
                beach=beach,
                point_name=point_name,
                sample_date=sample_date,
                classification=classification_from_label(raw_label),
                raw_classification=raw_label,
                line_number=line_number,
            )
        )

    if not rows:
        raise ImaSchemaError("bulletin PDF contained no point rows")
    if unparsed_headings:
        warnings.append(f"{unparsed_headings} point heading(s) had no parseable date/verdict")
    if known_municipalities and all(row.municipality is None for row in rows):
        warnings.append("no municipality heading matched; row join falls back to beach+point")

    exclusion_text = " ".join(
        line
        for line in lines
        if line.startswith("*")
        and re.search(r"Ponto", line, re.IGNORECASE)
        and re.search(r"coletad|descart|acesso|transporte", line, re.IGNORECASE)
    )
    excluded_numbers: set[int] = set()
    discarded_numbers: set[int] = set()
    for match in POINT_NUMBERS.finditer(exclusion_text):
        excluded_numbers.update(int(value) for value in re.findall(r"\d{1,3}", match.group(1)))
    for line in lines:
        if line.startswith("*") and re.search(r"descart|exclu", line, re.IGNORECASE):
            for match in POINT_NUMBERS.finditer(line):
                discarded_numbers.update(int(value) for value in re.findall(r"\d{1,3}", match.group(1)))

    return Bulletin(
        bulletin_date=bulletin_date,
        report_number=report_number,
        collection_dates=collection_dates,
        rows=tuple(rows),
        excluded_point_numbers=frozenset(excluded_numbers),
        discarded_point_numbers=frozenset(discarded_numbers),
        exclusion_text=exclusion_text,
        source_url=source_url,
        fetched_at=fetched_at,
        stale=stale,
        failed_pages=tuple(failed_pages),
        warnings=tuple(warnings),
    )


class BulletinRepository:
    def __init__(
        self,
        http: ImaHttpClient,
        cache: Cache,
        *,
        extractor: PdfExtractor | None = None,
        index_ttl: timedelta = INDEX_TTL,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._http = http
        self._cache = cache
        self._extractor = extractor or PypdfExtractor()
        self._index_ttl = index_ttl
        self._clock = clock

    async def latest_index(self) -> BulletinIndex:
        cached = await self._cache.get(INDEX_CACHE_KEY)
        if cached is not None:
            return parse_index(cached.text, fetched_at=cached.fetched_at)
        try:
            response = await self._http.get(INDEX_PATH)
        except Exception:
            stale = await self._cache.get(INDEX_CACHE_KEY, allow_stale=True)
            if stale is None:
                raise
            index = parse_index(stale.text, fetched_at=stale.fetched_at)
            return BulletinIndex(
                dates=index.dates,
                fetched_at=index.fetched_at,
                source_url=index.source_url,
                stale=True,
                warnings=("bulletin index refresh failed; serving stale index",),
            )
        index = parse_index(response.text, fetched_at=response.fetched_at)
        await self._cache.set(INDEX_CACHE_KEY, response.content, response.content_type, self._index_ttl)
        return index

    async def latest_date(self) -> date:
        return (await self.latest_index()).latest

    async def fetch(
        self,
        bulletin_date: date | None = None,
        *,
        known_municipalities: Sequence[str] = (),
    ) -> Bulletin:
        index = await self.latest_index()
        target = bulletin_date or index.latest
        cache_key = f"bulletin:pdf:{target.isoformat()}"
        cached = await self._cache.get(cache_key)
        stale = False
        warnings: list[str] = []
        if cached is not None:
            raw = cached.data
            fetched_at = cached.fetched_at
            content_type = cached.content_type
        else:
            try:
                response = await self._http.get(PDF_PATH.format(date=target.isoformat()))
            except Exception:
                stale_entry = await self._cache.get(cache_key, allow_stale=True)
                if stale_entry is None:
                    raise
                raw = stale_entry.data
                fetched_at = stale_entry.fetched_at
                content_type = stale_entry.content_type
                stale = True
                warnings.append("bulletin PDF refresh failed; serving stale cached PDF")
            else:
                raw = response.content
                fetched_at = response.fetched_at
                content_type = response.content_type
                await self._cache.set(cache_key, raw, content_type, PDF_TTL)
        if "application/pdf" not in content_type.lower() and not raw.startswith(b"%PDF"):
            raise ImaSchemaError("bulletin download was not a PDF")
        try:
            extracted = self._extractor.extract(raw)
        except Exception as exc:
            raise ImaSchemaError("bulletin PDF could not be extracted") from exc
        bulletin = parse_bulletin_text(
            extracted.text,
            source_url=BASE_URL + PDF_PATH.format(date=target.isoformat()),
            fetched_at=fetched_at,
            bulletin_date_hint=target,
            known_municipalities=known_municipalities,
            failed_pages=extracted.failed_pages,
            stale=stale,
        )
        if index.stale:
            warnings.append("bulletin index was stale")
        if warnings:
            bulletin = Bulletin(
                bulletin_date=bulletin.bulletin_date,
                report_number=bulletin.report_number,
                collection_dates=bulletin.collection_dates,
                rows=bulletin.rows,
                excluded_point_numbers=bulletin.excluded_point_numbers,
                discarded_point_numbers=bulletin.discarded_point_numbers,
                exclusion_text=bulletin.exclusion_text,
                source_url=bulletin.source_url,
                fetched_at=bulletin.fetched_at,
                stale=bulletin.stale,
                failed_pages=bulletin.failed_pages,
                warnings=(*bulletin.warnings, *warnings),
            )
        return bulletin
