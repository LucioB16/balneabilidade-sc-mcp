"""Typed provider errors.

The provider distinguishes an unavailable upstream, a changed schema, an
empty official result and an invalid caller argument. Tool layers must not
collapse these into a generic failure or a fabricated default.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date


class ImaError(Exception):
    """Base class for all IMA provider failures."""


class ImaNetworkError(ImaError):
    """DNS, TLS, timeout or connection failure before a usable response."""


class ImaHTTPError(ImaError):
    """The upstream returned a non-success HTTP status."""

    def __init__(self, status_code: int, url: str, message: str = "") -> None:
        self.status_code = status_code
        self.url = url
        detail = message or f"HTTP {status_code} from {url}"
        super().__init__(detail)


class ImaResponseTooLarge(ImaError):
    """The response exceeded the configured safety limit."""

    def __init__(self, url: str, limit: int) -> None:
        self.url = url
        self.limit = limit
        super().__init__(f"response from {url} exceeded {limit} bytes")


class ImaSchemaError(ImaError):
    """The response was reachable but did not have the expected shape."""


class ImaPdfParseIncomplete(ImaSchemaError):
    """The PDF was downloaded but its point table could not be trusted.

    The raw bytes are retained so a vision-capable client can read the original
    pages instead of receiving fabricated structured rows.
    """

    def __init__(
        self,
        message: str,
        *,
        pdf_bytes: bytes,
        bulletin_date: date | None,
        source_url: str,
    ) -> None:
        self.pdf_bytes = pdf_bytes
        self.bulletin_date = bulletin_date
        self.source_url = source_url
        super().__init__(message)


class ImaNotFound(ImaError):
    """The requested point, beach or year is not present in the official catalog."""


class ImaAmbiguousQuery(ImaError):
    """A name matched more than one beach and no municipality disambiguated it."""

    def __init__(self, query: str, candidates: Sequence[object]) -> None:
        self.query = query
        self.candidates = tuple(candidates)
        super().__init__(f"ambiguous query {query!r}: {len(self.candidates)} candidates")


class ImaInvalidArgument(ImaError, ValueError):
    """A caller supplied an invalid argument; this is not a provider outage."""


class ImaProviderUnavailable(ImaError):
    """No usable data could be obtained and no acceptable cache existed."""


class ImaNoData(ImaError):
    """The provider responded correctly but has no data for the request."""
