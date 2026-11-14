# Changelog

All notable changes are documented here. The project follows semantic
versioning once a stable public API is declared.

## [0.1.0] - 2026-11-14

### Added

- Evidence-based IMA/SC discovery and source comparison (JSON map, per-point
  analyses, CSV history, bulletin PDF).
- Normalized provider with typed models, typed errors, TTL cache, polite HTTP
  client and conservative freshness/exclusion handling.
- Latest-status reconciliation: bulletin PDF primary, CSV lab values, analyses
  fallback, map only for catalog/coordinates.
- CSV history with inclusive ranges, descending order, cursor pagination,
  qualifier/unit preservation, duplicate deduplication and explicit
  missing/unavailable/unmatched states.
- Local stdio MCP server with search_beaches, get_sampling_points,
  get_bathing_status, get_bathing_history and the vision fallback
  get_bulletin_page.
- Opt-in vision fallback that renders PDF pages as PNG when deterministic
  parsing is incomplete; it never fabricates rows.
- 71 offline tests, ruff and mypy checks; CI workflow for 3.11/3.12.
- Public documentation, MIT code license, attribution/security/release notes.

### Known limitations

- Local stdio only; no hosted transport, authentication or rate limiting.
- IMA/SC data has no confirmed reuse license; no datasets are redistributed.
- PDF parsing remains layout-dependent; the vision fallback is client-driven.
