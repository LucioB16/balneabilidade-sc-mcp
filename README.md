# Balneabilidade SC MCP

[![CI](https://github.com/LucioB16/balneabilidade-sc-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/LucioB16/balneabilidade-sc-mcp/actions/workflows/ci.yml)

**Local MCP server for official bathing-water data from Santa Catarina, Brazil.** It answers, per sampling point, what IMA/SC last published and when — and provides bounded, dated history. It is **not** a real-time water-quality sensor or a safety guarantee.

- Provider: [Instituto do Meio Ambiente de Santa Catarina (IMA/SC)](https://balneabilidade.ima.sc.gov.br/)
- Transport: local **stdio** (no hosted endpoint)
- Status: **0.1.0**, early public release
- Code license: **MIT** (data is not covered; see [attribution](docs/ATTRIBUTION.md))

## What it does

- Finds monitored beaches and distinguishes same-named beaches by municipality.
- Lists IMA sampling points with UUID, location and coordinates when published.
- Returns the latest **officially published dated** verdict for **each point**, with sample date, bulletin date, source and freshness.
- Returns dated CSV history with inclusive ranges, descending order and bounded pagination.
- Keeps mixed, partial, stale, excluded and unknown states explicit instead of converting them to "safe".
- Optionally renders bulletin pages as PNG when deterministic PDF parsing is incomplete, so a vision-capable client can read the original page.

## What it does not do

- It does not measure water quality in real time and does not guarantee that water is safe now.
- It does not cover other Brazilian states, weather, waves, jellyfish, rankings or tourist recommendations.
- It does not reclassify IMA results from E. coli counts.
- It does not expose a remote/public HTTP endpoint. Streamable HTTP is only a documented future option.

## Safety and freshness

IMA samples weekly in-season (October–March) and monthly off-season (April–September). A "proper" result means the agency classified a **dated sample** as proper, not that conditions are safe at the moment of the question.

The provider follows these rules:

- The latest bulletin PDF is authoritative for current status.
- Points outside the bulletin's collection window, or listed as not collected, are `carried_forward` — visible with their real older date, never presented as current.
- A sample explicitly discarded by IMA is `excluded`; its raw label is preserved but the point is `unknown`.
- The map's undated `CONDICAO` is used only for catalog/coordinates, never as status.
- A beach summary is `mixed` when points disagree and `partial` when some points are stale/excluded/unknown. Any improper point prevents a `proper` summary.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- An MCP client that supports stdio servers

## Install and run

```bash
git clone https://github.com/LucioB16/balneabilidade-sc-mcp.git
cd balneabilidade-sc-mcp
uv sync --extra mcp
uv run balneabilidade-sc-mcp
```

The last command starts the stdio server and waits for a client. Logs go to **stderr**; stdout is reserved for MCP protocol messages.

## MCP client configuration

Using `uv` (portable; adjust the absolute path):

```json
{
  "mcpServers": {
    "balneabilidade-sc": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/balneabilidade-sc-mcp",
        "run",
        "balneabilidade-sc-mcp"
      ]
    }
  }
}
```

On Windows, this also works:

```json
{
  "mcpServers": {
    "balneabilidade-sc": {
      "command": "C:\\path\\to\\balneabilidade-sc-mcp\\.venv\\Scripts\\balneabilidade-sc-mcp.exe",
      "args": []
    }
  }
}
```

See [docs/MCP_SERVER.md](docs/MCP_SERVER.md) for a verified example and troubleshooting.

## Tools

| Tool | Main inputs | What it returns |
|---|---|---|
| `search_beaches` | `query`, optional `municipality`, `limit` | Candidate beaches with municipality, point count and match type |
| `get_sampling_points` | `beach`, optional `municipality` | Point UUIDs, names, locations and coordinates |
| `get_bathing_status` | `beach`, optional `municipality`, `point_id` | Latest dated verdict per point, beach summary, freshness, provenance |
| `get_bathing_history` | `beach`, optional `municipality`, `point_id`, `from_date`, `to_date`, `limit`, `cursor` | Dated CSV records with qualifiers, unit, raw names and coverage |
| `get_bulletin_page` | `page`, optional `bulletin_date`, `dpi` | PNG page for vision fallback only |

## Example questions

Spanish:

- "¿Está apta para bañarse la Praia do Perequê, en Porto Belo? ¿En qué puntos y de qué fecha son los resultados?"
- "Mostrame el historial de Praia do Campeche entre diciembre de 2025 y marzo de 2026."
- "No sé el municipio; ¿qué playas se parecen a 'Praia Brava'?"

Portuguese:

- "Qual é a condição atual da Praia de Zimbros, em Bombinhas?"
- "Mostre o histórico da Praia do Campeche em 2025."
- "Quais são os pontos de coleta da Praia de Garopaba?"

A correct answer names the point(s), the **sample date**, the **bulletin date** and the source; it does not say "safe now".

## Status fields

| Field | Values |
|---|---|
| `classification` | `proper`, `improper`, `indeterminate`, `unknown` |
| `freshness` | `current`, `carried_forward`, `excluded`, `stale`, `unverified`, `unknown` |
| `summary.status` | `proper`, `improper`, `mixed`, `partial`, `unknown` |
| `source` | `bulletin_pdf`, `csv`, `analyses`, `catalog`, `cache` |

History returns `years_without_data` separately from `years_unavailable`, deduplicates exact duplicate measurements, preserves `<20`/`<10`/`> 24196` qualifiers and exposes `unmatched_names` when point names drift.

## Vision fallback

The deterministic PDF parser is primary. If it cannot validate a trustworthy point table, `get_bathing_status` includes `vision_fallback` metadata. A client with a vision-capable model can call `get_bulletin_page` and read the original PNG pages. The server does **not** call an LLM, does not fabricate rows and does not upgrade the status when a vision model might read a page.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv build
```

The offline suite has 71 tests and never calls IMA. The live discovery probe is separate and read-only:

```bash
python scripts/discovery_probe.py
```

CI runs lint, format check, mypy, offline tests and package build on Python 3.11 and 3.12. It does not require IMA credentials or network access.

## Troubleshooting

- **Ambiguous beach:** supply `municipality`; known duplicates include Praia Brava (Florianópolis/Itajaí) and Praia dos Ingleses (Florianópolis/São Francisco do Sul).
- **No data:** the tool returns `unknown`/`partial` with warnings; this is not a proper verdict.
- **Provider outage:** the provider may return a dated CSV/analyses fallback with `bulletin_unverified=true`; it never silently claims current proper status.
- **Vision fallback:** call `get_bulletin_page` only if the client supports images; mark unreadable pages as unverified.
- **Client cannot connect:** ensure the command is absolute or `uv --directory` points at the checkout, and that logs are read from stderr.

## Data provenance and attribution

Official data: **IMA/SC**, <https://balneabilidade.ima.sc.gov.br/>. Always cite the agency, report/bulletin number and sample date.

No explicit IMA data-reuse license was found. This repository does **not** redistribute IMA PDFs, CSV exports or bulk datasets; the provider fetches them at runtime. See [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md) before publishing data or derived datasets.

Reference implementation: [marola-dev/marola-app](https://github.com/marola-dev/marola-app) (MIT), reviewed at commit `7061a08e`. No Marola source code is copied.

## Limitations

- PDF parsing is layout-dependent; the fallback is client-driven, not a server-side OCR service.
- History is CSV-native; the PDF is authoritative only for the latest bulletin.
- Exact-name joins expose drift rather than guessing; a renamed point may appear as unmatched.
- Local stdio only: no remote transport, authentication, access control or rate limiting. Do not expose it to the internet without a separate security phase.
- No database: a small TTL file cache is used for catalog, PDFs and CSV.

## Project layout

```text
src/balneabilidade_sc_mcp/
  provider.py       source reconciliation, freshness, history
  bulletin.py       portal index, PDF parsing, exclusions
  history.py        CSV export/parser
  catalog.py        map catalog and matching
  server.py         MCP stdio tools
  pdf_vision.py     PNG rendering fallback
docs/               discovery, contract, provider, server, release, attribution
tests/              71 offline tests with synthetic fixtures
```

## Documentation

- [Discovery report](docs/DISCOVERY_REPORT.md)
- [Product contract](docs/PRODUCT_CONTRACT.md)
- [Provider](docs/PROVIDER.md)
- [MCP server](docs/MCP_SERVER.md)
- [Release notes](docs/RELEASE.md)
- [Attribution and data licensing](docs/ATTRIBUTION.md)
- [Security policy](SECURITY.md)

## License

Code and documentation: **MIT** — see [LICENSE](LICENSE). The MIT license does not cover IMA/SC data or third-party material.
