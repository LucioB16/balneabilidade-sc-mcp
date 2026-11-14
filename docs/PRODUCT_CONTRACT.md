# MCP product contract (provisional; refine after discovery)

## Objective
Enable a Spanish- or Portuguese-speaking user to ask an MCP-equipped agent about official bathing-water quality in **Santa Catarina** and the dated history of its monitoring points. **Never imply live sensor accuracy** from weekly/monthly samples.

## Planned tools (MVP)

### `search_beaches`
Input: `query` (required string), `municipality` (optional string), `limit` (bounded integer). Output: list of candidate beach/locality identifiers, official name, municipality, sampling point count if known, match explanation and provenance. Never guess one match if ambiguous.

### `get_sampling_points`
Input: `beach` (name or verified identifier), `municipality` optional. Output: IMA monitoring points with stable/native IDs when available, human-readable locations, coordinates if published, and source. Flag naming collisions and missing location metadata.

### `get_bathing_status`
Input: `beach` (required), `municipality` optional, `point_id` optional. Output: officially reported latest **dated** result for each matching point; original classification label, normalized condition, source_url, `sample_date`, `bulletin_date` if known, `fetched_at` and `age_days` when computable, plus a conservative beach summary. If a date is absent, expose `undated` or `unknown` rather than "safe now". If beach points conflict, return `mixed` and details; don't hide improper points. For stale datasets, do not report a current `proper` beach status.

### `get_bathing_history`
Input: `beach` (required), `municipality` optional, `point_id` optional, `from_date` and `to_date` optional ISO calendar dates, bounded `limit`, cursor if needed. Output: ordered records by point with dates, official condition, measured values/units/qualifiers if published, source URL, year coverage and next cursor. Return explicit no-data for unmonitored years, preserve records with censored lab values (e.g. `<20`), don't infer missing samples.

## Normalized output invariants
- Every response includes `provider="IMA/SC"`, the source and retrieval timestamp; include collection/publication dates where discoverable.
- Point status enumeration: `proper`, `improper`, `indeterminate`, `unknown`. Beach aggregation may also be `mixed` or `partial`; `stale` and `undated` are separate data-quality flags, not a valid certificate to enter the water.
- Any missing date, nonmatching identifier or upstream error is explicit and never defaults to `proper`.
- Classification is IMA's official one; **do not reclassify** from E. coli numbers or partial sample windows.
- Avoid accidental overstatement such as “safe right now”; use: “Latest published IMA sample for Ponto X, dated YYYY-MM-DD, was ...”.
- Date semantics: IMA local `America/Sao_Paulo`, API responses ISO 8601 for normalized fields, preserve raw Portuguese dates/labels in source metadata as useful.
- API schema, canonical identifier and freshness threshold are to be finalized using Phase 1 evidence.

## Representative acceptance questions (not hard-coded fixtures)
- “¿Está apta para bañarse Praia do Perequê, en Porto Belo? ¿En qué puntos y de qué fecha son los resultados?”
- “¿Y en Garopaba? Mostrame cada punto si las condiciones son distintas.”
- “Qual é a condição atual da Praia do Campeche? De quando são as amostras?”
- “Mostrame el historial de Praia do Campeche entre diciembre de 2025 y marzo de 2026.”
- “No conozco el municipio, ¿qué playas se parecen al nombre que escribí?”

## Explicitly out of scope
Other Brazilian states; ocean wave/temperature forecasts; advisories unsupported by IMA; tourist accommodation/booking; ambient sensor telemetry; a hosted public endpoint without auth. Future features require deliberate scope change.
