# Agent instructions — Balneabilidade SC MCP

## Mission and scope
Build a reliable, public, open-source-ready **Model Context Protocol (MCP) server** for querying official bathing-water quality information for **Santa Catarina, Brazil only**, using the Instituto do Meio Ambiente de Santa Catarina (IMA/SC) as the authoritative data provider. The initial user-facing goals are: (1) ask whether a named beach or its monitored sampling points are suitable for bathing **according to the latest available official sample**, and (2) inspect dated historical results. No weather, surfing forecast, jellyfish forecasts, ranking algorithm, or other Brazilian states are in scope.

The directory initially contains **bootstrap documentation, not an implemented or validated server**. Treat every technical assertion in `docs/RESEARCH_BASELINE.md` as a research lead unless reproduced; verify the current service before implementing it. Marola is a reference implementation, not a dependency. Read its code and license before reusing material.

## Mandatory workflow
1. Read `PLAN.md` at the start of each session. It is the authoritative ordered task list. Change `- [ ]` to `- [x]` only after work is verified; add newly necessary tasks to the applicable phase. Keep `docs/DISCOVERY_REPORT.md` and decisions current.
2. **The first executable action is creating and verifying a new PUBLIC GitHub repository** (after basic local safety checks, authentication checks and `.gitignore`). Do it before networking discovery or product code. The repository is intended to be `balneabilidade-sc-mcp` under the authenticated GitHub account. Never create it as private, silently reuse a conflicting repository, or assume credentials exist. If authenticated creation/push is impossible, report and stop this phase, preserving local state. User explicitly authorized the public repo and remote workflow.
3. Execute **only the first/next incomplete phase** in `PLAN.md` in a run. The first phase includes repository publication AND discovery. Validate, commit, push, report, and **STOP for authorization** before the next phase. Do not use an implied `/goal` feature or run all phases in one go without an explicit later instruction.
4. For every meaningful independently verified milestone, immediately commit the relevant code, tests and docs together with the current `PLAN.md`. Finish each verified phase with a checkpoint commit if needed; don't generate empty commits. Push to the authorized `origin` after validated commits and verify the remote, but never force-push. Report hashes and any uncommitted work.
5. Inspect `git status`, the working tree, existing remotes and staged diff before any destructive or publishing action. Don't overwrite unrelated work. Don't stage credentials, secrets, environment files, caches, vendor blobs, unlicensed datasets or unrelated files.

## Source-of-truth and methodology
- Official portal: https://balneabilidade.ima.sc.gov.br/
- Reference: https://github.com/marola-dev/marola-app (MIT; confirm current license, review exact commit). Study its IMA JSON, PDF and historical CSV adapters, tests, and https://github.com/marola-dev/marola-app/issues/57 before designing our provider.
- `docs/RESEARCH_BASELINE.md` records leads from 2026-11-14; `docs/DISCOVERY_REPORT.md` is the investigation's evidence-based output; `docs/PRODUCT_CONTRACT.md` describes initial agent-facing behavior. Update them when evidence contradicts assumptions.
- Prefer documented or empirically verified live requests over assumptions inferred from source code. Record HTTP method, path, form fields, response content type, anonymized representative shape, tested UTC timestamp, result and limitations. Never invent a successful request, a schema, a data license, a limit or a sampled date.
- Fetch only modest samples, apply timeouts, cache requests and back off on server errors. Respect provider restrictions, provenance, attribution and privacy. Never stress-test endpoints or scrape unnecessarily.

## Safety-critical interpretation rules
- **Not real-time sensing.** “Apta ahora” must mean the latest officially published dated result, with exact sampling/publication dates and freshness caveat, never a live measurement or guarantee.
- Model **sampling points separately from beaches**. A beach may have mixed results; never silently convert a single point verdict into a beach-wide verdict. Report each point and its location when available.
- Preserve IMA classification including proper/improper/indeterminate/unknown and distinguish `mixed`, `partial`, `stale` and `undated` in any beach summary. No data is not proper. Stale or unverified results must not be presented as current.
- Prefer source metadata (`sample_date`, `bulletin_date`, `fetched_at`, `source_url`, `point_id` and `data_age_days` where computable) to confident-sounding prose. Portuguese official terminology must not be mistranslated or normalized into incorrect safety statements.
- The `/relatorio/mapa` endpoint reportedly stopped carrying dated `ANALISES` in October 2026. Do not assume those arrays exist. Design a tested fallback: official historical CSV by beach/year and/or latest dated PDF bulletin, with conservative reconciliation by municipality, beach and sampling point.
- Resolve ambiguous names safely (municipality qualifier, distinct sampling points, canonical accents). If one user query matches several beaches, return candidates instead of choosing arbitrarily.
- For remote MCP deployment (if later authorized), require authentication, access controls and abuse prevention. Local stdio is MVP. Never leak diagnostics to the stdio protocol stream: logs go to stderr.

## Technical approach — provisional until discovery
Prefer **Python 3.11+, uv, official modelcontextprotocol/python-sdk v2 (`MCPServer`)**, httpx, typed models, pytest and ruff if they pass the live discovery and package verification; don't copy obsolete v1 FastMCP examples into a v2 implementation. Keep IMA-specific HTTP adapters separate from parser, normalization, data model, cache, service layer and MCP tools. Offline fixture tests must pass without IMA internet access. Package it for a clean clone and reproducible local execution; provide verified agent setup examples. No database is necessary for MVP unless history caching requirements demonstrate a need.

## Engineering and reporting
- Write code and public developer documentation in English; preserve Portuguese field names in raw source adapters; user-facing MCP descriptions should work for Spanish and Portuguese questions. Report progress to the user in Spanish.
- Use explicit errors and partial results instead of fabricated defaults; bounded retries, clear provenance, small TTL cache and safe fetch limits. Distinguish transient provider outage from empty official results.
- Each phase requires automated verification when applicable, manual reproduction notes for live probes, updated checkboxes and a pushed milestone. End each run with summary, URLs, tested commands, real commit hashes, unresolved risks, and the phase awaiting approval.
- Keep this file concise. Detailed investigation, schemas, fixtures and setup belong in focused `docs/` files or code comments.
