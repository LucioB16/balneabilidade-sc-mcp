# Balneabilidade SC MCP

**Status: Phase 2 provider implemented and tested offline. The MCP server is not implemented yet.**

Repository: <https://github.com/LucioB16/balneabilidade-sc-mcp>

Goal: a small Model Context Protocol server that lets an AI agent retrieve the **latest published official bathing-water assessment** and **sampling history** for beaches in Santa Catarina, Brazil. It resolves municipality, beach and monitoring point, and says exactly **when** the reported condition was sampled and published. Official IMA sampling is not a real-time measurement.

## What discovery established (2026-11-14)

- `POST /relatorio/mapa` returns the 260-point catalog with UUIDs and coordinates, but **no dated samples** and an **undated** `CONDICAO`. It is not a current-status source.
- `POST /relatorio/analisesPonto` returns the last five **dated** analyses per point. It is undocumented and includes samples that the bulletin later discards.
- The **latest bulletin PDF** (currently 53/2026, 2026-11-13) is the authoritative dated publication. It lists 257 current points plus 3 carried/excluded rows (Pontos 83, 94 and 96 in Florianópolis). A 45-day age rule alone would wrongly accept two of them.
- `POST /relatorio/exportarCSV` provides 2003–2026 history with lab values, but no point UUID or coordinates; joins must use municipality + beach + point names.
- CSV and PDF dated results matched for all 105 points compared across four municipalities; JSON analyses matched CSV for all 85 rows compared.

## Documentation

- [Execution plan](PLAN.md)
- [Discovery report with live evidence, comparisons and recommended architecture](docs/DISCOVERY_REPORT.md)
- [MCP product contract (schemas and status semantics)](docs/PRODUCT_CONTRACT.md)
- [Provider implementation and live verification](docs/PROVIDER.md)
- [Research baseline: leads vs verified evidence](docs/RESEARCH_BASELINE.md)

## Provider (Phase 2)

The normalized provider reads the latest bulletin PDF, joins it to the canonical catalog, enriches the sample with CSV lab values, and falls back conservatively to CSV/analyses when the bulletin is unavailable. It does not use the map's undated `CONDICAO` as a status.

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run mypy src
```

Usage and implementation details are in [docs/PROVIDER.md](docs/PROVIDER.md). The offline suite has 49 tests and does not call IMA; the live probe below is separate.

## Reproduce the discovery

A read-only, stdlib-only probe (a handful of requests; not part of CI) checks the catalog, dated analyses, CSV export and latest bulletin PDF:

```bash
python scripts/discovery_probe.py
```

## Important caveats

- **Not real-time.** "Proper" means the latest official dated sample/classification, not a guarantee for today. Rain, runoff and other conditions can change water quality quickly.
- **Point-level truth.** A beach may have mixed results. 97 beaches have one point; others have up to 10. Never convert one point's verdict into a beach-wide guarantee.
- **No confirmed data license.** No license/terms were found on the IMA portal or in the Santa Catarina open-data catalog. This repository does not redistribute IMA datasets or PDFs. Do not assume the data is open-licensed; see the discovery report.
- **No project license yet.** A public repository is not automatically open source. Licensing is a Phase 5 decision.
- **No MCP server yet.** The provider is a Python library. MCP tools, stdio configuration and client examples are Phase 3.

## Reference implementation

[marola-dev/marola-app](https://github.com/marola-dev/marola-app) (MIT) is a reference, not a dependency. Its IMA JSON adapter expected `ANALISES`, which the feed no longer carries; its PDF fallback and name-join approach were reviewed at commit `7061a08e`. Any copied code must preserve the MIT notice and attribution.

## Next step

Phase 3: expose the provider through MCP tools over stdio and test it with an actual MCP client. **Awaiting user approval before starting.**
