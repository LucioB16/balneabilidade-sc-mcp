# Research baseline (leads vs verified evidence)

Last prepared: **2026-11-14**. Read this with [`DISCOVERY_REPORT.md`](DISCOVERY_REPORT.md), which contains the full evidence, commands, timestamps and response shapes. This file records the original leads and what the live checks changed.

## Verification status (2026-11-14)

| Original lead | Verdict | Evidence |
|---|---|---|
| Official portal at <https://balneabilidade.ima.sc.gov.br/> | **Confirmed** | 200 HTML, 50,466 B, latest bulletin link `2026-11-13`; index lists 10 recent bulletins (2026-09-10 … 2026-11-13). |
| Latest report 53/2026 dated 2026-11-13 | **Confirmed** | PDF `relatorio_n53-2026.pdf`, `DATA: 13/11/2026`, samples 09–11/11/2026, 19 pages, 317,885 B. |
| `POST /relatorio/mapa` returns points/coordinates with top-level `CONDICAO` | **Confirmed, with corrections** | 260 points, 28 municipalities, 208 `PRÓPRIO` / 52 `IMPRÓPRIO`, UUID `CODIGO`; **no `ANALISES` in any object**; `CONDICAO` is **undated**. 85,280 B (not ~207 KB). |
| Map had 337 points and no dated `ANALISES` (Marola issue #57, 2026-10-06) | **Confirmed at that time; count changed** | Issue #57 body: 337 points, no dated samples. Live 2026-11-14: 260 points. Do not hard-code counts. |
| `/municipio/getMunicipios` | **Confirmed** | 28 objects; `CODIGO` is the **municipality name**, not a numeric ID; `DESCRICAO` same. |
| `/local/getLocaisByMunicipio` with `municipioID` | **Confirmed** | POST form field is the municipality **name**; returns `CODIGO` (beach name), `BALNEARIO`, `MUNICIPIO`, lat/lon. `municipioID=0` returns literal `null`, not all. |
| `/pontoColeta/getPontosByLocal` with `localID` | **Confirmed** | POST form field is the beach **name**; returns point UUID, name, `OCULTAR`, location, coords, `CONDICAO`. `localID=0` returns `null`. |
| `/registro/anosAnalisados` | **Confirmed** | 24 years, 2026 down to 2003. |
| `/relatorio/exportarCSV` with `municipioID`,`localID`,`ano` | **Confirmed, with more detail** | UTF-8 BOM, LF, 13 columns, `dd/MM/yyyy`, `HH:mm`, conditions `PRÓPRIA`/`IMPRÓPRIA`, qualifiers `<20`/`<10`/`> 24196`/`>24196`, `Sem registros` short rows, 137-byte header-only empty result. Names, not IDs. POST required; GET ignores fields. |
| `/relatorio/historico` | **Confirmed** | 200 HTML (76 KB) for the selected point; same data as CSV; not recommended as primary. |
| `/relatorio/downloadPDF/<date>` | **Confirmed, with more detail** | 200 `application/pdf`; latest date discovered from index; 260 rows parsed; 257 current + 3 carried/excluded; unknown date → 404. |
| Undocumented `/relatorio/analisesPonto` | **New finding** | Portal JS calls it with `codigo=<UUID>`; returns `application/json` with the last 5 dated analyses (`DATA`, `CONDICAO`, `CHUVA`, `RESULTADO`, `TEMP_AGUA`). Not in the baseline and not used by Marola's current client. |
| CORS absent | **Confirmed** | No `Access-Control-Allow-Origin` with `Origin`; `OPTIONS` timed out at 20 s. Server-side MCP is required for browser-independent use. |
| Marola MIT license | **Confirmed at pinned commit** | `marola-dev/marola-app` @ `7061a08e643c5fe05485cb2917be405f5b1ab8c4`, MIT, copyright 2026 marola.dev. |
| Marola PDF fallback / JSON adapter | **Confirmed by code inspection** | `ImaScWaterQualityClient` expects `ANALISES`; `ImaScPdfWaterQualityClient` discovers the latest PDF from the index and joins rows on folded beach+point; `WaterQuality.isFresh` uses a 45-day window. Code was read, not executed. |
| CSV adapter in Marola | **Not shipped** | CSV is designed in `marola-dev/marola` MIP-0056; no CSV adapter code found in `marola-app` at the pinned commit (only test fixtures under `oods/src/test/resources/ima-sc`). |
| IMA data license | **Unresolved / no license found** | No terms/license on the portal; `robots.txt` 404; `dados.sc.gov.br` CKAN search for `balneabilidade` returned 0 datasets; MIP-0056 records the same finding. Public availability ≠ reuse license. |

## Official data source

- Portal: <https://balneabilidade.ima.sc.gov.br/>
- Latest bulletin at check: **53/2026, 2026-11-13**, samples collected **09, 10 and 11 November 2026**.
- Classification labels: `Próprio`, `Impróprio`, `Indeterminado`. `Indeterminado` did not appear in the current map/CSV/PDF snapshot, but must remain supported.
- **Not real-time.** Weekly in-season (October–March); monthly off-season (April–September). The PDF's own methodology page says samples are collected weekly October–March and monthly April–September.
- The PDF can carry forward older dates for points not collected (Ponto 83/94/96 in bulletin 53) and can include legitimately ~30-day-old monthly rows in the off-season (bulletin 46, 2026-09-24).

## Existing public clients

- Marola: <https://github.com/marola-dev/marola-app> (MIT at pinned commit `7061a08e643c5fe05485cb2917be405f5b1ab8c4`).
  - JSON adapter: `local/src/main/scala/marola/water/ImaScWaterQualityClient.scala`
  - PDF fallback: `local/src/main/scala/marola/water/ImaScPdfWaterQualityClient.scala`, `ImaScPdfParser.scala`, `PdfLines.scala`
  - Tests: `local/src/test/scala/marola/water/ImaSc*Spec.scala`
- Issue #57: <https://github.com/marola-dev/marola-app/issues/57> — created and closed 2026-10-06; documents the loss of `ANALISES` and the PDF fallback.
- MIP-0056 (CSV/open-data design, not shipped code): <https://github.com/marola-dev/marola/blob/main/docs/MIPs/MIP-0056-oods-open-ocean-data-store.md> — confirms the CSV fields, 2003–2026 coverage, BOM, 13 columns, `<20` handling, name-based join, and the license gap.
- Another Python client: <https://github.com/soutobias/oceanobs/blob/dev/oceanobs/water_quality/sc.py> — not used as evidence; review only if it adds a tested adapter.
- Official Python MCP SDK: <https://github.com/modelcontextprotocol/python-sdk> and <https://py.sdk.modelcontextprotocol.io/> — v2 uses `MCPServer`; the pinned version is recorded in PROVIDER.md. Do not copy v1 `FastMCP` examples.

## Endpoint hypotheses — corrected status

| Candidate | Verified method/body | Purpose | Verified result |
|---|---|---|---|
| `/relatorio/mapa` | POST empty (GET also worked) | Point catalog + undated condition | 260 points, no `ANALISES`, no date |
| `/municipio/getMunicipios` | POST empty | Municipality names | 28; `CODIGO` = name |
| `/local/getLocaisByMunicipio` | POST `municipioID=<name>` | Beaches per municipality | name-keyed; 0 → `null` |
| `/pontoColeta/getPontosByLocal` | POST `localID=<name>` | Points per beach | UUIDs; 0 → `null` |
| `/registro/anosAnalisados` | POST empty | Years | 2003–2026 |
| `/relatorio/analisesPonto` | POST `codigo=<UUID>` | Last 5 dated analyses | **New**; `application/json`; includes discarded sample |
| `/relatorio/exportarCSV` | POST `municipioID`, `localID`, `ano` | Dated history | names; BOM; 13 cols; `Sem registros` edge cases |
| `/relatorio/historico` | POST same + `redirect=true` | HTML history | per-point HTML; same values |
| `/relatorio/downloadPDF/<YYYY-MM-DD>` | GET | Bulletin PDF | authoritative dated verdicts; 260 rows |

## Important unresolved considerations

1. **No official API contract.** The routes are portal-internal and undocumented. The map shape changed once (ANALISES removed; point count 337 → 260), so shape validation, fixtures and fallbacks are mandatory.
2. **No confirmed reuse license.** Do not redistribute IMA data/PDFs in the repository or publish a bulk dataset until a deliberate policy/decision. Attribution is required in practice; the project's own source license is also still undecided.
3. **Staleness is not just age.** Bulletin 53 carries Ponto 83 (05/11, discarded), Ponto 94 (19/10, not collected) and Ponto 96 (26/05, not collected). A 45-day rule accepts 83 and 94. Use the bulletin's collection window/exclusion footnote, and a season-aware age threshold; never use map `CONDICAO` as current status.
4. **Point vs beach.** Beaches have 1–10 points; 97 have exactly one. Never turn one point's proper verdict into a beach-wide guarantee. Report mixed/partial explicitly.
5. **Name joins.** CSV and PDF have no point UUID. Use (municipality, beach, point) with accent/case folding. 88 distinct point names for 260 points; duplicate beach names exist (Praia Brava in Florianópolis and Itajaí, etc.).
6. **PDF parsing is fragile.** Page 19 raised `PdfReadError` under the system pypdf 6.16.2; the pinned 6.21.4 extracted all pages, but the risk remains. Two headings wrap across lines, 73 headings need 3–7 lines of lookahead, and fonts/encodings vary. Reflow headings, search until the next heading, catch page-level failures, validate row/key counts, and expose partial results rather than guessing.
7. **CORS/rate limits.** No CORS headers and `OPTIONS` timed out; no rate-limit headers/robots. Use a server-side stdio MCP, cache, low volume and backoff. Do not load-test.
8. **HTTP/HTTPS and timezone.** HTTP 301s to HTTPS. Sample dates are official local calendar dates (`America/Sao_Paulo`); do not shift them.
