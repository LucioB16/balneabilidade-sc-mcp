# Execution plan — Balneabilidade SC MCP

## Execution contract
This is a **phased** project. Execute only the next incomplete phase per run, then stop and request authorization to proceed. **Phase 1 includes public GitHub repository creation as its first operational step, followed by source discovery.** Do not start feature implementation during Phase 1. Follow `AGENTS.md` for safe Git commits, remote pushes, truthful checkbox updates and publication verification. All unchecked items are pending; mark `- [x]` only after verification. Record real Git SHAs in the end-of-phase report; do not pre-fill them.

## Phase 1 — Public repo creation + evidence-based IMA discovery (FIRST)
- [x] Inspect existing workspace, `git status`, `.git/config`, and repository remotes before modifications; preserve pre-existing work.
- [x] Verify `.gitignore` excludes credentials, .env files, local cache, data dumps and generated artifacts; set up or reuse Git safely (`main` when new).
- [x] Check GitHub CLI (`gh`) availability/authentication and determine the actual authenticated owner; check whether the proposed repository name already exists; don't hijack a conflicting repo.
- [x] **CREATE the GitHub repository publicly NOW** (`balneabilidade-sc-mcp`), attach `origin`, publish a safe initial documentation/plan commit, and verify repo URL, visibility = PUBLIC and `git ls-remote origin`. Stop and report a blocker if this cannot be verified. Do not do discovery first.
- [x] Read the current official IMA/SC portal, its loaded JavaScript/HTML (including actual XHR endpoints), and latest published bulletin listing. Cite URLs and retrieval date.
- [x] Inspect Marola's relevant IMA adapters and tests at a pinned commit: `ImaScWaterQualityClient`, `ImaScPdfWaterQualityClient`, history/CSV paths, fixtures, and issue #57. Record what is reusable conceptually, its limitations and MIT attribution obligations if copying code.
- [x] Probe the live endpoints conservatively: `/relatorio/mapa`, `/municipio/getMunicipios`, `/local/getLocaisByMunicipio`, `/pontoColeta/getPontosByLocal`, `/registro/anosAnalisados`, `/relatorio/exportarCSV`, `/relatorio/historico`, and `/relatorio/downloadPDF/<published-date>`. Confirm *actual* HTTP methods, required form payloads, redirects, status codes, content types, response schemas and errors; do not assume all endpoints are stable.
- [x] Test at least three **actually monitored** beaches or municipalities (prefer examples from Porto Belo/Perequê, Garopaba and Itapoá if IMA lists them); identify duplicate names, one-vs-many points, proper/improper/mixed or indeterminate cases if present, accent normalization and no-data cases. Never fabricate test results.
- [x] Independently verify whether the map JSON includes `ANALISES`, its record count and whether `CONDICAO` is undated; compare latest bulletin and CSV results for at least two matching points with dated samples.
- [x] Verify historical CSV request semantics (whether municipality and beach are names or IDs), year coverage, date formats, encoding/BOM, decimal conventions, header changes, empty results, date ordering, and point reconciliation.
- [x] Evaluate fresh-status strategy: prefer dated CSV or latest PDF with matching points; document source precedence, freshness thresholds/proposal, mismatch behavior and how to return `unknown` instead of a misleading "safe today" claim.
- [x] Investigate CORS (only if browser access matters), rate-limit signals, access/robots/terms, data licensing/attribution, error handling, request volume and caching recommendations. Do not run load tests.
- [x] Update `docs/DISCOVERY_REPORT.md` with an evidence table, reproducible sanitized curl commands, live response-shape examples (no large dataset dumps), alternatives compared, confidence/risk and a recommended architecture.
- [x] Update `docs/PRODUCT_CONTRACT.md` with empirically grounded tool schemas and point/beach status semantics; write a small validated proof-of-connectivity if it materially supports discovery, but **do not** build the MCP server yet.
- [x] Validate discovery reproduction, update completed `PLAN.md` tasks, commit verified discovery milestones and final phase checkpoint with current docs, push and verify remote public files. Report links, commit hash(es) and findings. **STOP pending approval for Phase 2.**

## Phase 2 — Normalized IMA provider and reliable latest observations
- [x] Confirm the Python/uv/official MCP SDK choice against currently installed versions; record lockfile and dependency choices; scaffold maintainable Python package and tests.
- [x] Build HTTP client (timeouts, bounded retries, polite headers, cache, typed provider errors, resilient content-type parsing) and canonical municipality/beach/point catalog using the validated routes.
- [x] Build normalized models for sampling locations, latest dated measurements, classification, source provenance and confidence/freshness; preserve unknown/indeterminate states.
- [x] Implement latest-sample retrieval with discovered source priority (JSON with dates when available, validated CSV or PDF when needed); join points conservatively and expose unmatched observations.
- [x] Write fixture-driven unit tests for current and historical feed shapes, empty arrays, UUID IDs, renamed beaches, mixed results, stale data, missing dates, Unicode, timezones and provider failures.
- [x] Run lint, type checks where configured and full offline test suite; update docs/plan and commit/push verified milestones and phase checkpoint. **STOP.**
- [x] Add opt-in vision fallback: keep deterministic parsing primary, render bulletin pages as PNG only when completeness checks fail, and expose the fallback through the provider/MCP without fabricating rows.

## Phase 3 — MCP tools and local client integration
- [x] Implement `search_beaches` and `get_sampling_points` with unambiguous matching, useful candidate lists and stable structured outputs.
- [x] Implement `get_bathing_status` returning the latest dated official verdict **for each point**, explicit beach summary status (including mixed/partial/unknown), sample date, bulletin date, source and freshness fields.
- [x] Expose MCP via local stdio first using the verified official SDK; no stdout logging; schemas and error responses are discoverable and documented.
- [x] Test tools with an actual MCP client/inspector, including Spanish and Portuguese queries, ambiguous names and multi-point beaches, provider outage and no-data scenarios.
- [x] Update README with verified stdio setup and at least one working client configuration; run tests/lint; commit/push and stop.

## Phase 4 — Historic observations and comparison
- [x] Implement `get_bathing_history` over official dated records with municipality/beach/point filters, inclusive date range, descending ordering and bounded pagination.
- [x] Preserve raw IMA record provenance, sampling date, result counts/units, qualifiers (`<20` and similar) and classification when available; do not invent missing periods or recompute official classification.
- [x] Handle historical naming/point identifier drift and conflicting CSV/PDF rows transparently; document precedence and unresolved matches.
- [x] Add tests across years, year boundaries, duplicate measurements, missing years, empty results and date/time locale behavior.
- [x] Verify at least one end-to-end historical query and one latest-status query with real source evidence; update docs/plan and commit/push. **STOP.**

## Phase 5 — Public product quality and handoff
- [x] Write polished public README (scope, current-vs-real-time caveat, installation, MCP configuration, tools, bilingual example questions, troubleshooting, data provenance/attribution and limitations).
- [x] Agree on project license and publish its actual text when authorized; do not imply that a public repo is automatically licensed. Preserve attribution if Marola code is copied.
- [x] Add GitHub Actions CI for reproducible format/lint/tests/build on a clean checkout; no credentials or calls to IMA required in default CI.
- [x] Add release/version metadata and a documented installation command; evaluate optional Streamable HTTP **only as a documented future option**, not an unauthorized public deployment.
- [x] Validate a clean clone, install, stdio handshake, discovery of all MCP tools, current + historical queries, graceful provider failure, and source/freshness communication.
- [ ] Inspect security, public content, licenses, git status, CI results and `gh repo view` public visibility; mark verified DoD boxes, commit/push and report repository URL and SHA.

## Definition of Done — verifiable
- [x] A NEW public GitHub repository was created at project start and its public visibility remains verified.
- [ ] The IMA/SC discovery report documents live requests, timestamps, changing API shapes, sources and viable fallbacks.
- [ ] A clean clone can run the MCP server locally using documented commands.
- [ ] An MCP client can find a Santa Catarina beach and distinguish similarly named beaches or multiple sampling points.
- [ ] `get_bathing_status` reports **latest available dated official** point-level observations with source and freshness, not an unsupported live-water claim.
- [ ] `get_bathing_history` returns accurate, bounded, date-filtered records for monitored points and handles missing history honestly.
- [ ] Offline automated tests and GitHub CI pass, including stale/mixed/empty/provider-outage regressions.
- [ ] README, attribution/licensing status, limitations, release instructions and all verified `PLAN.md` checkboxes are published in the public repo.
