# MCP product contract

**Status:** design contract grounded in the 2026-11-14 live discovery in [`DISCOVERY_REPORT.md`](DISCOVERY_REPORT.md). The normalized provider is implemented and offline-tested ([provider notes](PROVIDER.md)); the local stdio MCP tools are implemented and client-tested ([server notes](MCP_SERVER.md)).

## Objective

Enable a Spanish- or Portuguese-speaking agent to ask about official bathing-water quality in **Santa Catarina, Brazil**, and get:

1. the **latest officially published dated** result for a named beach and each of its IMA sampling points; and
2. dated history, with source, sample date, bulletin date and freshness.

This is **not real-time sensing**. IMA samples weekly in-season and monthly off-season. A response must never say "safe right now" or imply a live measurement.

## Source semantics (non-negotiable)

- Authoritative latest source: the **latest IMA bulletin PDF** discovered from the portal index, with its dated point rows, collection window and exclusion footnote.
- History source: the official **CSV export** by municipality + beach + year.
- Per-point cross-check/fallback: `POST /relatorio/analisesPonto` (last five dated samples).
- Catalog/IDs/coordinates: `POST /relatorio/mapa`; this route's `CONDICAO` is **undated** and is not a status source.
- If the bulletin cannot be parsed/verified, return `bulletin_unverified=true` and a conservative status; never upgrade to a clean beach-level "proper". Include `vision_fallback` metadata and let a vision-capable client read the original pages; the server never invents the missing rows.
- Never reclassify from E. coli counts. The official `CONDICAO` is IMA's rolling classification.
- Preserve `Indeterminado`/`unknown`; never map missing data to proper.

## Tool: `search_beaches`

Resolve a free-text beach query to candidate catalog entries. Since IMA has no independent beach UUID, the stable key is derived from municipality + official beach name.

**Input**

| Field | Type | Required | Notes |
|---|---|---|---|
| `query` | string | yes | Beach or locality name; accents optional; 2–120 chars. |
| `municipality` | string | no | Municipality name; use when known to disambiguate. |
| `limit` | integer | no | 1–20, default 10. |

**Output**

```json
{
  "provider": "IMA/SC",
  "query": "praia brava",
  "matches": [
    {
      "beach_key": "florianopolis|praia-brava",
      "beach_name": "Praia Brava",
      "municipality": "Florianópolis",
      "point_count": 4,
      "match_type": "exact_folded",
      "source_url": "https://balneabilidade.ima.sc.gov.br/"
    }
  ],
  "ambiguous": true,
  "fetched_at": "2026-11-14T22:10:00Z",
  "warnings": []
}
```

Rules:

- Fold Unicode accents/case and whitespace; preserve the official name in `beach_name`.
- If several municipalities match without a qualifier, return all candidates and `ambiguous=true`; never pick one arbitrarily.
- If no match, return an empty list and a helpful warning; do not guess.
- `beach_key` is a stable normalized identifier internal to this provider (municipality + beach), not an IMA code.
- `point_count` comes from the cached catalog; it may change over time.

## Tool: `get_sampling_points`

Return the IMA monitoring points for one resolved beach.

**Input**

| Field | Type | Required | Notes |
|---|---|---|---|
| `beach` | string | yes | Official name or `beach_key`. |
| `municipality` | string | no | Required in practice for duplicate names. |
| `include_hidden` | boolean | no | Default false; hidden points are exposed only with a warning. |

**Output**

```json
{
  "provider": "IMA/SC",
  "beach_key": "porto-belo|praia-de-pereque",
  "beach_name": "Praia de Perequê",
  "municipality": "Porto Belo",
  "points": [
    {
      "point_id": "390f41d4-e7d0-4642-baf4-b6ae2ceb111a",
      "point_name": "Ponto 03",
      "location": "Avenida Senador Atílio Fontana, n°266, foz do Rio Perequizinho",
      "latitude": -27.1555249,
      "longitude": -48.5643452,
      "hidden": false
    }
  ],
  "source": "ima_sc_catalog",
  "source_url": "https://balneabilidade.ima.sc.gov.br/relatorio/mapa",
  "fetched_at": "2026-11-14T22:10:00Z",
  "warnings": []
}
```

Rules:

- `point_id` is the IMA UUID `CODIGO`; it is the canonical key for `analisesPonto` and for status/history selection.
- A beach can have 1–10 points. Never merge a river-mouth/lagoon point into the adjacent ocean beach (e.g. `Praia de Itapoá - no rio` is a separate beach with its own point).
- If the catalog has no coordinates, return nulls and a warning; do not invent coordinates.
- If the beach is ambiguous, return `ambiguous_query` with candidates instead of a points list.

## Tool: `get_bathing_status`

Return the latest **officially published dated** result for each matching point, plus a conservative beach summary.

**Input**

| Field | Type | Required | Notes |
|---|---|---|---|
| `beach` | string | yes | Official name or `beach_key`. |
| `municipality` | string | no | Required when the beach name is duplicated. |
| `point_id` | string | no | Restrict to one IMA UUID; must belong to the beach. |

**Output**

```json
{
  "provider": "IMA/SC",
  "query": {"beach": "Praia de Zimbros", "municipality": "Bombinhas"},
  "bulletin": {
    "report_number": "53/2026",
    "bulletin_date": "2026-11-13",
    "collection_dates": ["2026-11-09", "2026-11-10", "2026-11-11"],
    "source_url": "https://balneabilidade.ima.sc.gov.br/relatorio/downloadPDF/2026-11-13",
    "fetched_at": "2026-11-14T22:10:00Z"
  },
  "beach_summary": {
    "status": "mixed",
    "points_total": 2,
    "points_current": 2,
    "points_improper": 1,
    "points_stale": 0,
    "points_excluded": 0,
    "points_unknown": 0,
    "has_improper": true
  },
  "points": [
    {
      "point_id": "d0b03259-b472-48eb-b1ee-ebe76452d52c",
      "point_name": "Ponto 09",
      "classification": "improper",
      "raw_classification": "IMPRÓPRIA",
      "sample_date": "2026-11-09",
      "bulletin_date": "2026-11-13",
      "sample_age_at_bulletin_days": 4,
      "data_age_days": 5,
      "freshness": "current",
      "ecoli": {"value": 1046, "qualifier": "exact", "unit": "NMP/100mL"},
      "rain": "Ausente",
      "water_temp_c": 19.0,
      "source": "ima_sc_bulletin_pdf+ima_sc_csv",
      "source_url": "https://balneabilidade.ima.sc.gov.br/relatorio/downloadPDF/2026-11-13",
      "warnings": []
    },
    {
      "point_id": "c3f580b1-db45-422d-8d46-0dca3361f0b8",
      "point_name": "Ponto 10",
      "classification": "proper",
      "raw_classification": "PRÓPRIA",
      "sample_date": "2026-11-09",
      "bulletin_date": "2026-11-13",
      "sample_age_at_bulletin_days": 4,
      "data_age_days": 5,
      "freshness": "current",
      "ecoli": {"value": 789, "qualifier": "exact", "unit": "NMP/100mL"},
      "rain": "Ausente",
      "water_temp_c": 19.0,
      "source": "ima_sc_bulletin_pdf+ima_sc_csv",
      "source_url": "https://balneabilidade.ima.sc.gov.br/relatorio/downloadPDF/2026-11-13",
      "warnings": []
    }
  ],
  "provenance": {
    "latest_source": "bulletin_pdf",
    "history_values_source": "csv",
    "cross_check_source": "analises_ponto",
    "bulletin_unverified": false
  },
  "warnings": [
    "Beach-level result is mixed: at least one point is improper. Check each point before entering the water."
  ]
}
```

When the deterministic bulletin parser is incomplete, the result also carries `vision_fallback` with `reason`, `bulletin_date`, `source_url`, `page_count`, `pages_available` and instructions. It does not change the status by itself.

### Status enums

Point `classification`:

- `proper` — IMA label `PRÓPRIO`/`PRÓPRIA` in a valid published result.
- `improper` — IMA label `IMPRÓPRIO`/`IMPRÓPRIA`.
- `indeterminate` — IMA label `INDETERMINADO` (not observed in the current snapshot; must be supported).
- `unknown` — no dated official result, unparseable result, or explicit no-data. **Never** proper.

Point `freshness`:

- `current` — row is in the latest bulletin, not excluded, and within the cadence window.
- `carried_forward` — row is present but older than the cadence window (e.g. 94/96).
- `excluded` — explicitly excluded/discarded in the bulletin (e.g. 83).
- `stale` — cached/older data outside the window.
- `unverified` — bulletin unavailable/unparseable; status from CSV/analyses with a conservative age check.
- `unknown` — no dated sample.

Beach `status`:

- `proper` — every point current and proper; still report dates.
- `improper` — every point improper.
- `mixed` — proper and improper coexist (e.g. Zimbros 09/11/2026).
- `partial` — at least one point is stale/excluded/unverified/unknown, and no improper overrides it.
- `unknown` — no valid point result.

Rules:

- If **any** point is improper, the summary must not be `proper`.
- If proper and improper coexist, `mixed` with `has_improper=true` and per-point detail.
- If any point is excluded/stale/unknown, do not certify the whole beach; use `partial` with counts and warnings.
- If the queried beach name is ambiguous, return candidates (do not choose).
- If `point_id` is supplied but belongs to another beach, return an explicit error.
- CSV E. coli/rain/temperature values may be absent when the CSV is unavailable; the bulletin verdict and dates still stand. Do not infer values.
- Always include `sample_date`, `bulletin_date` (when known), source and `fetched_at`. A response without a sample date is not a status.
- A stale or unverified result must not be presented as current; use "latest published sample dated …" language.

### Freshness policy (implemented; calibration continues)

- In-season (October–March, weekly): current if `sample_age_at_bulletin_days <= 10`.
- Off-season (April–September, monthly): current if `sample_age_at_bulletin_days <= 40`.
- The bulletin's stated collection dates and exclusion footnote take precedence over the numeric threshold.
- 45 days alone is insufficient: Ponto 83 (8 days, discarded) and Ponto 94 (25 days, not collected) would pass. See discovery section 6.
- The provider distinguishes a **discarded** sample (`freshness=excluded`, classification withheld as unknown, raw label preserved) from a **not-collected/carried** point (`freshness=carried_forward`, dated verdict visible with an age warning). It parses the bulletin footnote and the stated collection dates rather than inferring from age alone.
- When the bulletin is unavailable, use `bulletin_unverified=true` and a conservative window; never use the map `CONDICAO`.

## Tool: `get_bulletin_page` (vision fallback)

Only for a vision-capable client when `get_bathing_status` returns a non-null `vision_fallback`. The deterministic parser remains primary; this tool renders the original PDF page instead of fabricating missing rows.

**Input**

| Field | Type | Required | Notes |
|---|---|---|---|
| `page` | integer | no | 1-based page number; default 1. |
| `bulletin_date` | ISO date | no | Defaults to the latest bulletin. |
| `dpi` | integer | no | 72–200; default 120. |

**Output**

- A text block with page metadata (page, page count, source, date).
- An `image/png` content block with the rendered page.
- No structured point rows: the client model reads the image and must mark unreadable pages as unverified.

Rules:

- `vision_fallback` is present when more than `max(2, 5%)` of catalog points are missing from the parsed table, or a heading has no parseable date/verdict.
- The status result stays conservative (`bulletin_unverified=true` or `partial`/`unknown`) even if a vision model might read the page.
- Do not use `get_bulletin_page` as a primary parsing path or send image content to a model without vision.
- The server does not call an LLM; the client decides whether to use vision.

## Tool: `get_bathing_history`

Return dated official records for one beach/point over a bounded date range.

**Input**

| Field | Type | Required | Notes |
|---|---|---|---|
| `beach` | string | yes | Official name or `beach_key`. |
| `municipality` | string | no | Required for duplicate names. |
| `point_id` | string | no | Restrict to one IMA UUID; otherwise all points of the beach. |
| `from_date` | ISO date | no | Inclusive; defaults to 1 January of the current year in `America/Sao_Paulo`. |
| `to_date` | ISO date | no | Inclusive; defaults to today in `America/Sao_Paulo`. |
| `limit` | integer | no | 1–200, default 50. |
| `cursor` | string | no | Opaque pagination cursor. |

**Output**

```json
{
  "provider": "IMA/SC",
  "beach": {"beach_key": "porto-belo|praia-de-pereque", "beach_name": "Praia de Perequê", "municipality": "Porto Belo"},
  "range": {"from_date": "2026-01-01", "to_date": "2026-11-14"},
  "records": [
    {
      "point_id": "390f41d4-e7d0-4642-baf4-b6ae2ceb111a",
      "point_name": "Ponto 03",
      "municipality": "Porto Belo",
      "beach": "Praia de Perequê",
      "raw_point_name": "Ponto 03",
      "location": "Avenida Senador Atílio Fontana, n°266, foz do Rio Perequizinho",
      "csv_year": 2026,
      "sample_date": "2026-11-09",
      "classification": "proper",
      "raw_classification": "PRÓPRIA",
      "ecoli": {"value": 373, "qualifier": "exact", "unit": "NMP/100mL"},
      "rain": "Ausente",
      "wind": "Sudeste",
      "tide": "Enchente",
      "water_temp_c": 21.0,
      "air_temp_c": 20.0,
      "source": "csv",
      "source_url": "https://balneabilidade.ima.sc.gov.br/relatorio/exportarCSV"
    }
  ],
  "coverage": {"years_requested": [2026], "years_with_data": [2026], "years_without_data": [], "years_unavailable": []},
  "next_cursor": null,
  "duplicate_samples": 0,
  "unmatched_samples": 0,
  "unmatched_names": [],
  "source": "csv",
  "fetched_at": "2026-11-14T22:10:00Z",
  "warnings": []
}
```

Rules:

- Order descending by `sample_date`, then point; bounded `limit`; no unbounded dumps.
- Preserve qualifiers: `<20`, `<10`, `> 24196`, `>24196`; do not coerce to a number and do not drop the record.
- Preserve official labels and raw values; do not recompute the classification.
- Handle `Sem registros` as no data for that point/year, not as a sample.
- Years outside 2003–2026 or with no rows: return explicit `years_without_data` and empty records, not a fabricated period.
- A year that could not be fetched is `years_unavailable`, not `years_without_data`; the result is partial, not silently empty.
- Exact duplicate measurements (same point, date and time) are deduplicated and counted in `duplicate_samples`; the warning is explicit.
- Name drift is exposed through `unmatched_samples`/`unmatched_names`; never fuzzy-match or renumber a historical point.
- History is CSV-native. The latest bulletin PDF remains authoritative for current status; if a CSV row for the same sample disagrees with the bulletin verdict, the status keeps the PDF verdict and warns.
- If a year has no CSV data but the point has a bulletin row, optionally include it with source `bulletin_pdf` and a warning.
- Historical naming drift: CSV has no point UUID; join by (municipality, beach, point) and expose `unmatched` rows. Do not silently drop.

## Normalized output invariants

- Every response: `provider: "IMA/SC"`, `source`/provenance, `fetched_at` (UTC ISO 8601), and dates as calendar dates in `America/Sao_Paulo` (no UTC shifting).
- No "safe today"/"apta agora" without the sample date and bulletin date; preferred phrasing: "Latest published IMA sample for Ponto X, dated YYYY-MM-DD (bulletin YYYY-MM-DD), was …".
- Point-level truth first; beach summary is derived and conservative.
- Missing data, unmatched joins, upstream errors and parse failures are explicit. No default `proper`.
- No raw upstream HTML/stack traces in tool output; log sanitized diagnostics to stderr.
- Tool descriptions and examples should be discoverable in Spanish and Portuguese; field names stay English.

## Representative acceptance questions

These are grounded in the discovered data, not hard-coded fixtures:

- "¿Está apta para bañarse Praia do Perequê, en Porto Belo? ¿En qué puntos y de qué fecha son los resultados?" → 3 points, all proper, sample 2026-11-09, bulletin 2026-11-13.
- "¿Y en Garopaba? Mostrame cada punto si las condiciones son distintas." → 2 points, both proper, sample 2026-11-10; also 3 other Garopaba beaches.
- "Qual é a condição atual da Praia de Zimbros, em Bombinhas?" → mixed: Ponto 09 improper, Ponto 10 proper, both 2026-11-09.
- "Mostrame el historial de Praia do Campeche entre diciembre de 2025 y marzo de 2026." → CSV rows; 5 points; handle `Sem registros` and censored values.
- "No conozco el municipio, ¿qué playas se parecen al nombre que escribí?" → candidates, e.g. Praia Brava in Florianópolis vs Itajaí; never choose silently.
- "¿La muestra de Ponta das Canas es actual?" → Ponto 83 is excluded/discarded in bulletin 53; report the exclusion and the date, not a current verdict.
- "¿Qué pasó con Beira-Mar Norte y Lagoa da Conceição?" → carried forward (19/10 and 26/05), not current.

## Explicitly out of scope

Other Brazilian states; wave/temperature/weather forecasts; jellyfish; advisories not supported by IMA; tourist accommodation; ambient sensor telemetry; a hosted public endpoint without authentication; ranking algorithms; reclassification from lab counts.

## Open decisions before release

- Data-reuse/license policy for IMA content (none found; do not publish datasets).
- IMA/SC data-reuse license remains unresolved; project code is MIT (see LICENSE and ATTRIBUTION.md).
- Final season-aware thresholds after testing more bulletins.
- Whether to expose raw bulletin provenance fields on every point or only at the response level (default: response-level plus per-point source URL).
