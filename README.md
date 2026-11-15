<p align="center">
  <sub><strong>English</strong> · <a href="README.es-AR.md">Español (AR)</a> · <a href="README.pt-BR.md">Português (BR)</a></sub>
</p>

<p align="center">
  <img src="assets/brand/wave-mark.svg" width="64" alt="Balneabilidade SC MCP wave mark">
</p>

# Balneabilidade SC MCP

<p align="center">
  <strong>Ask your agent about the water at the beach.</strong><br>
  A local MCP server for dated samples published by IMA/SC, point by point.
</p>

<p align="center">
  <a href="#installation">Installation</a> ·
  <a href="#manual-install">Manual install</a> ·
  <a href="#tools">Tools</a> ·
  <a href="#what-a-response-includes">Response</a>
</p>

<p align="center">
  <a href="https://github.com/LucioB16/balneabilidade-sc-mcp/actions/workflows/ci.yml"><img src="https://github.com/LucioB16/balneabilidade-sc-mcp/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-0B6E99" alt="MIT license"></a>
</p>

> **Dated samples, not live readings.** The card below is a real MCP response excerpt. The sample was collected on 2026-11-09 and published on 2026-11-13, so it does not describe the water today. IMA/SC sampling is weekly in-season and monthly off-season.

| Latest published sample | Praia de Zimbros · Bombinhas |
|:--|:--|
| Ponto 09 | `improper` · 1,046 NMP/100mL |
| Ponto 10 | `proper` · 789 NMP/100mL |
| Sample date | 2026-11-09 |
| Bulletin | 2026-11-13 |
| Beach summary | `mixed` (the points disagree) |

The response lists each sampling point with its sample date and bulletin date. One point does not decide the beach.

## What you can ask

- “What is the latest published result for Praia de Zimbros, and when was it sampled?”
- “Show every sampling point; are the conditions mixed?”
- “Show the 2025 history for Praia de Zimbros, with dates and lab values.”
- “Which beaches are called Praia Brava?” The answer lists candidates when several beaches share the name.

## Installation

### Install with your agent

Copy this prompt into a coding agent. It includes the repository and the setup guide, so the agent does not need to search for either.

```text
Install the Balneabilidade SC MCP server from:
https://github.com/LucioB16/balneabilidade-sc-mcp

Setup guide:
https://github.com/LucioB16/balneabilidade-sc-mcp/blob/main/docs/MCP_SERVER.md

Do it locally. Do not search for the project or the documentation elsewhere.

Requirements:
- Clone the repository into a directory I confirm.
- Use uv: run `uv sync --extra dev` and `uv run pytest`.
- Register a local stdio MCP server named `balneabilidade-sc`:
  `uv --directory <checkout> run balneabilidade-sc-mcp`
- If you cannot edit my MCP client configuration, print the exact JSON and tell me where to paste it.
- Verify the client lists all five tools and run one query for "Praia de Zimbros", municipality "Bombinhas".
- Show me the configuration and the verification output.

Do not expose the server over the network. Ask before modifying files outside the project or any global configuration. Do not install globally. Do not commit credentials or local configuration.
```

If `uv` is not installed, ask before installing it. Manual setup is below.

### Manual install

```bash
git clone https://github.com/LucioB16/balneabilidade-sc-mcp.git
cd balneabilidade-sc-mcp
uv sync --extra mcp
uv run balneabilidade-sc-mcp
```

The last command starts the stdio server and waits for a client. Logs go to stderr; stdout carries the MCP protocol.

Add it to an MCP client with `uv --directory` (adjust the absolute path):

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

On Windows, the installed executable also works:

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

## Tools

| Tool | Main inputs | What it returns |
|:--|:--|:--|
| `search_beaches` | `query`, optional `municipality`, `limit` | Candidate beaches, municipality, point count and match type |
| `get_sampling_points` | `beach`, optional `municipality` | Point UUIDs, locations and coordinates |
| `get_bathing_status` | `beach`, optional `municipality`, `point_id` | Latest dated result per point, beach summary, freshness and provenance |
| `get_bathing_history` | `beach`, optional `municipality`, `point_id`, `from_date`, `to_date`, `limit`, `cursor` | Dated CSV records with qualifiers, unit, raw names and coverage |
| `get_bulletin_page` | `page`, optional `bulletin_date`, `dpi` | PNG page for vision fallback only |

## What a response includes

Every dated point result carries:

| Field | Meaning |
|:--|:--|
| `classification` | `proper`, `improper`, `indeterminate` or `unknown` |
| `freshness` | `current`, `carried_forward`, `excluded`, `stale`, `unverified` or `unknown` |
| `sample_date` | The date the sample was collected |
| `bulletin_date` | The date the publishing bulletin was issued, when known |
| `source` / `source_url` | `bulletin_pdf`, `csv`, `analyses`, `catalog` or `cache`, plus the source URL |
| `summary.status` | `proper`, `improper`, `mixed`, `partial` or `unknown` |

A point that IMA/SC did not collect, or one whose sample was discarded, is not presented as current. The point keeps its raw label and an explicit freshness flag. Any improper point prevents a `proper` beach summary.

## History

`get_bathing_history` reads the CSV exports published by IMA/SC:

- inclusive `from_date`/`to_date` and descending order;
- bounded pagination with a cursor;
- raw point names, location and `csv_year`;
- E. coli values with `<20`/`<10`/`> 24196` qualifiers and the `NMP/100mL` unit;
- `years_without_data` separated from `years_unavailable`;
- exact duplicate rows are deduplicated and counted;
- point-name drift is exposed in `unmatched_names` instead of being guessed;
- when CSV and the latest bulletin disagree about the same sample, the bulletin verdict is kept and a warning is returned.

History comes from the CSV exports. The latest bulletin PDF is the reference for current status.

## Example questions

- “What is the latest published result for Praia de Zimbros, and when was it sampled?”
- “Show every sampling point; are the conditions mixed?”
- “Show the 2025 history for Praia de Zimbros, with dates and lab values.”
- “Which beaches are called Praia Brava?”

A useful answer gives the point, the sample date and the bulletin date. It does not say “safe now”.

## Vision fallback

The deterministic PDF parser is primary. If it cannot validate a trustworthy point table, `get_bathing_status` includes `vision_fallback` metadata. A client with a vision-capable model can call `get_bulletin_page` and read the original PNG pages. The server only returns page images. It does not call an LLM or create rows, and it leaves the status unchanged.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv build
```

The offline suite has 75 tests and never calls IMA. The read-only discovery probe is separate:

```bash
python scripts/discovery_probe.py
```

CI runs lint, format check, mypy, offline tests and package build on Python 3.11 and 3.12. It needs no credentials and makes no IMA calls.

## Data, attribution and license

The source is the **Instituto do Meio Ambiente de Santa Catarina (IMA/SC)**, <https://balneabilidade.ima.sc.gov.br/>. Always cite the agency, the report/bulletin number, the sample date and the source URL.

No data-reuse license was confirmed for IMA/SC material. This repository does not redistribute PDFs, CSV exports or bulk datasets; the provider fetches them at runtime. See [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md) before publishing derived data.

Code and documentation are MIT licensed. The license does not cover IMA/SC data. See [LICENSE](LICENSE).

## Limitations

- PDF parsing depends on layout. The vision fallback runs in the client; the server does not run OCR.
- History comes from CSV; the PDF is the reference only for the latest bulletin.
- Exact-name joins expose drift instead of guessing; renamed points may appear as unmatched.
- The default command remains local stdio. An optional stateless Streamable HTTP app is available for hosted clients; review [remote HTTP deployment](docs/REMOTE_HTTP.md) before exposing it.
- The remote endpoint is unauthenticated and read-only. Provider pacing is per process; use ingress rate limits and a single replica unless shared cache and global request limiting are configured.
- The provider uses a small TTL file cache instead of a database.
- This is not a medical or safety guarantee.

## Documentation

- [Discovery report](docs/DISCOVERY_REPORT.md)
- [Product contract](docs/PRODUCT_CONTRACT.md)
- [Provider](docs/PROVIDER.md)
- [MCP server](docs/MCP_SERVER.md)
- [Remote Streamable HTTP deployment](docs/REMOTE_HTTP.md)
- [Release notes](docs/RELEASE.md)
- [Attribution and data licensing](docs/ATTRIBUTION.md)
- [Security policy](SECURITY.md)

## Project layout

```text
src/balneabilidade_sc_mcp/
  provider.py       source reconciliation, freshness, history
  bulletin.py       portal index, PDF parsing, exclusions
  history.py        CSV export/parser
  catalog.py        map catalog and matching
  server.py         MCP tools shared by stdio and Streamable HTTP
  http_server.py    hosted Streamable HTTP entry point
  pdf_vision.py     PNG rendering fallback
docs/               discovery, contract, provider, server, release, attribution
tests/              75 offline tests with synthetic fixtures
```
