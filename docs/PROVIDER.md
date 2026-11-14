# IMA/SC provider — Phase 2 implementation

**Status:** normalized provider implemented and tested offline. The MCP server is **not implemented yet** (Phase 3). This document records the implementation choices and the live verification performed on 2026-11-14.

Related: [Discovery report](DISCOVERY_REPORT.md) · [Product contract](PRODUCT_CONTRACT.md) · [Plan](../PLAN.md)

## Toolchain verified for this phase

| Tool | Verified version | Notes |
|---|---|---|
| Python | 3.12.4 | Pinned in `.python-version`; project requires 3.11+. |
| uv | 0.11.28 | Lockfile committed as `uv.lock`. |
| httpx | 0.28.1 | Async client with injectable transport for tests. |
| pypdf | 6.21.4 | PDF extraction; page-level tolerance retained. |
| tzdata | 2026.6 | Required for `America/Sao_Paulo` on Windows. |
| pytest | 8.4.2 | Offline unit/integration tests. |
| ruff | 0.17.5 | Lint + format checks. |
| mypy | 1.20.2 | Static check of `src`. |
| mcp | 2.3.0 | Verified `mcp.server.MCPServer` exists; installed only with the `mcp` extra in Phase 3. |

The MCP SDK is intentionally **not** a default dependency: Phase 2 is a provider, and Phase 3 will add the stdio server and its integration test. The `mcp>=2.3,<3` extra records the verified v2 API and avoids v1 `FastMCP` examples.

## Package layout

```text
src/balneabilidade_sc_mcp/
  models.py          typed enums/dataclasses: classification, freshness, source, point status
  normalization.py   accent folding, dates, E. coli qualifiers, season, collection dates
  errors.py          typed network/HTTP/schema/not-found/ambiguous/provider errors
  cache.py           TTL memory/file cache with explicit stale reads
  http.py            polite async HTTP client, bounded retries, size limits, typed errors
  catalog.py         /relatorio/mapa -> canonical municipality/beach/point catalog + search
  bulletin.py        index discovery, pypdf extraction, bulletin parsing, exclusions
  history.py         /relatorio/exportarCSV POST + CSV parsing
  analyses.py        /relatorio/analisesPonto last-five adapter
  provider.py        source reconciliation, freshness, beach summary, history pagination
tests/               offline synthetic fixtures and 49 tests
```

## Source policy implemented

1. **Latest official status:** newest bulletin PDF discovered from the portal index. The PDF supplies `bulletin_date`, per-point `sample_date`/verdict, collection dates and the exclusion/carry-forward footnote.
2. **CSV enrichment:** the same sample date is joined to the CSV for the beach/year to add E. coli, rain, wind, tide and temperatures. CSV never overrides the PDF verdict; a disagreement is a warning.
3. **Fallback without a bulletin:** latest CSV sample for the current/previous year, then `analisesPonto`, with `bulletin_unverified=true` and conservative freshness.
4. **Map:** catalog UUIDs, names and coordinates only. Its undated `CONDICAO` is never used as a status.

## Latest-status rules

- Join priority: `(municipality, beach, point)` → `(beach, point)` only if unique → otherwise explicit unmatched/unknown.
- `discarded` footnote points become `freshness=excluded` and `classification=unknown` with the raw label preserved (Ponto 83).
- Points outside the bulletin's stated collection dates, or older than the cadence window, become `carried_forward` (Pontos 94/96).
- In-season (October–March) window: **10 days**. Off-season (April–September) window: **40 days**. The bulletin's stated dates and footnote take precedence over the numeric window.
- `data_age_days` uses the provider's `today` in `America/Sao_Paulo`; `sample_age_at_bulletin_days` uses the bulletin date. Dates are calendar dates, never UTC-shifted.
- Beach summary: `proper` only if every point is current and proper; `mixed` if proper and improper coexist; `improper` if all improper; `partial` if some point is stale/excluded/unknown and no improper overrides it; `unknown` otherwise. Any improper point prevents a `proper` summary.

## Catalog and matching

- `parse_catalog` validates the JSON array, requires UUID `CODIGO`, rejects duplicate point UUIDs, parses coordinates with range checks and keeps warnings instead of inventing values.
- `Catalog.beaches` groups by `slugify(municipality)|slugify(beach)`; search folds accents/case and returns `exact`/`prefix`/`contains` candidates across municipalities.
- `resolve_beach` never chooses between duplicate names (for example Praia Brava in Florianópolis and Itajaí); the caller must supply a municipality.
- The point UUID is the canonical identity. CSV/PDF name fields remain raw in models.

## CSV history rules

- `POST /relatorio/exportarCSV` with `municipioID`, `localID` and `ano`; the request is form-encoded with UTF-8 names.
- `utf-8-sig` with BOM; LF; 13 columns; tolerant header (the official temperature columns contain a `}` typo).
- Short `Sem registros` rows are no-data markers, not samples. Empty exports are valid no-data.
- E. coli qualifiers `<20`, `<10`, `> 24196` and `> 24196` are preserved as `(value, qualifier, raw)`.
- History is grouped by point and sorted descending; provider sorts globally by `(sample_date, point_name)` and paginates with a non-negative integer cursor.
- Date ranges are bounded to 10 years per query; history starts in 2003; future `to_date` is rejected.

## Cache policy

| Resource | Key | TTL |
|---|---|---|
| Catalog | `catalog:relatorio:mapa` | 24 h |
| Bulletin index | `bulletin:index` | 1 h |
| Bulletin PDF | `bulletin:pdf:<date>` | 10 years (immutable by date) |
| CSV | `csv:<municipality>|<beach>|<year>` | current year 6 h; past years 30 d |
| Analyses | `analyses:<point_id>` | 1 h |

The default is `FileCache(".cache/balneabilidade")`; tests use `MemoryCache`. Expired entries are returned only with `allow_stale=True` and the provider adds a warning. Empty/partial responses never replace a good cache entry.

## Error handling

- `ImaNetworkError`: timeout/transport after bounded retries.
- `ImaHTTPError`/`ImaNotFound`: non-success status; 404 is separate.
- `ImaResponseTooLarge`: safety limit (10 MB default).
- `ImaSchemaError`: reachable but wrong JSON/PDF/CSV shape.
- `ImaAmbiguousQuery`: duplicate beach names without municipality.
- `ImaInvalidArgument`: caller error (bad year/range/cursor/UUID).
- `ImaProviderUnavailable`: no usable data and no cache.

The provider catches upstream failures for status/history fallbacks but never turns an unknown into proper. Raw upstream HTML/stack traces are not surfaced in models.

## Usage

```python
import asyncio
from balneabilidade_sc_mcp import ImaProvider

async def main() -> None:
    async with ImaProvider() as provider:
        status = await provider.get_bathing_status("Praia de Perequê", municipality="Porto Belo")
        print(status.summary.status, len(status.points), status.bulletin.bulletin_date)
        for point in status.points:
            print(point.point.point_name, point.classification, point.sample_date, point.freshness)

asyncio.run(main())
```

## Commands

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run mypy src
python scripts/discovery_probe.py   # live, read-only Phase 1 probe
```

Offline tests never call IMA. The live probe is intentionally separate and is not run by CI.

## Live verification (2026-11-14)

With the default cache and a fixed `today=2026-11-14`:

- Bulletin PDF parsed to **260 rows / 28 municipalities**, collection dates **09–11/11/2026**, exclusions `{83,94,96}`, discarded `{83}`, no parse warnings.
- `Praia de Perequê / Porto Belo`: 3 points, all `proper/current`, E. coli values 373, 272 and 122 from the CSV.
- `Praia de Zimbros / Bombinhas`: `mixed` (Ponto 09 improper 1046; Ponto 10 proper 789).
- `Praia de Ponta das Canas / Florianópolis`: `mixed`; Ponto 83 is `excluded`/`unknown` with raw `IMPRÓPRIA`, while current points 23/67/70 remain visible.
- `Beira-Mar Norte / Florianópolis`: `improper`; Ponto 94 is `carried_forward` (19/10/2026) while 11 and 95 are current.
- `Lagoa da Conceição / Florianópolis`: `mixed`; Ponto 96 is `carried_forward` (26/05/2026) while current points remain visible.
- History for Perequê 2026 returned descending dated records with pagination.

## Known limitations and Phase 3 work

- The PDF parser depends on pypdf text extraction. The live 2026-11-13 PDF needs lookahead up to 7 lines per heading; a 2-line window yields only **187/260 rows**. The implementation searches forward until the next heading, so wrapped addresses do not lose the verdict.
- pypdf 6.16.2 failed on page 19 of this PDF; pypdf 6.21.4 extracts all pages. Page-level tolerance remains because future PDFs can regress.
- No real IMA PDF/CSV is committed: fixtures are synthetic and only reproduce the shapes. Data reuse/licensing remains unresolved; see the discovery report.
- The MCP server, tool schemas, and stdio diagnostics are Phase 3. This phase does not expose any network service or MCP endpoint.
- The provider's public API is Python classes/async methods, not yet a stable MCP contract.
