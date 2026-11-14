# IMA/SC Discovery Report

**Status:** discovery complete; provider, MCP server and release are documented in the linked docs.

**Investigation date:** 2026-11-14, 19:04–19:13 `America/Buenos_Aires` (UTC−3) = 2026-11-14T22:04–22:13Z. Sampling dates use `America/Sao_Paulo` (also UTC−3 on this date).

**Repository:** <https://github.com/LucioB16/balneabilidade-sc-mcp>

**Bootstrap commit at investigation start:** `d1b42a4052e7eefc62d68fe4e5b77731abd83286`

**Marola reference commit inspected:** `7061a08e643c5fe05485cb2917be405f5b1ab8c4` (MIT; commit date 2026-10-20, main head at check).

> All findings below are from live requests executed during this investigation or from source inspected at the pinned commit. No response was invented. HTTP calls were modest, read-only, and used a descriptive User-Agent. No load testing was performed.

## 1. Executive summary

1. **`POST /relatorio/mapa` still returns the point catalog, but not dated samples.** On 2026-11-14 it returned **260 points** with UUID `CODIGO`, municipality/IBGE code, beach name, point name, location, coordinates and an **undated** `CONDICAO`. No object contained an `ANALISES` key. This reproduces the core of Marola issue #57 (which reported 337 points and no `ANALISES` on 2026-10-06); the point count is not stable and must not be hard-coded.
2. **A second, undocumented endpoint supplies dated point-level samples.** The portal's own JavaScript calls `POST /relatorio/analisesPonto` with `codigo` = point UUID and receives the **last five dated analyses** (`DATA`, `CONDICAO`, `CHUVA`, `RESULTADO`, `TEMP_AGUA`) as `application/json`. It is not mentioned in the research baseline and is not used by Marola's current IMA client.
3. **The weekly PDF is the authoritative dated bulletin.** The latest index link was **2026-11-13** (report **53/2026**), with samples collected on **09, 10 and 11 November 2026**. Parsed with `pypdf` (page-level error tolerance plus heading reflow), the PDF yielded **260 point rows**, matching the 260 live catalog points by normalized (beach, point) name. The bulletin's prose says **257 points** were monitored that week; the three extra rows are carried or excluded and are the safety-critical exception (section 6).
4. **CSV is the reliable history source, but it has no point IDs.** `POST /relatorio/exportarCSV` with `municipioID` (municipality **name**), `localID` (beach **name**) and `ano` returns UTF-8-BOM CSV for 2003–2026, 13 columns, `dd/MM/yyyy`, with censored values such as `<20`, `<10`, `> 24196` and `>24196`. Joining on (`Municipio`, `Balneario`, `Ponto Coleta`) matched **100%** of rows in the four municipalities tested. Point names alone are **not unique** (88 distinct names for 260 points).
5. **Source comparison found no contradiction between CSV and PDF dated results.** For 105 points across Porto Belo, Garopaba, Itapoá and Florianópolis, the latest CSV row and the PDF row had identical sample dates and semantically identical conditions. The JSON `analisesPonto` rows matched the CSV for all 85 rows compared. The differences are in coverage and context, not in the verdicts.
6. **The map's `CONDICAO` is not a current-status source.** It matched the PDF's latest row for all 260 points, but three of those rows are not current-valid: Ponto 83 (05/11/2026, sample **discarded** in the bulletin), Ponto 94 (19/10/2026, **not collected**) and Ponto 96 (26/05/2026, **not collected**). The map is undated, so it cannot distinguish these. A 45-day freshness rule alone would wrongly accept Ponto 83 (8 days) and Ponto 94 (25 days).
7. **There is no public API contract, license or CORS support.** The portal sets a PHP session cookie but requires no authentication/CSRF token. JSON endpoints usually answer `text/html` even when the body is JSON; only `analisesPonto` returned `application/json`. There is no `Access-Control-Allow-Origin`, `OPTIONS` did not answer within 20 s, `HEAD /relatorio/mapa` did not answer within 30 s, `robots.txt` is 404, and no reuse license/terms were found on the portal or in the Santa Catarina open-data CKAN search. Attribution is required in practice; bulk redistribution must not be assumed licensed.

**Recommended architecture:** latest-status reads the **latest bulletin PDF** (authoritative dated verdicts, collection context and exclusions), uses **CSV** for dated history and for lab values, and uses `analisesPonto` as a cheap per-point cross-check/fallback. The **map is used only for catalog, UUIDs, coordinates and names** — never as the status source. Full recommendation in section 8.

## 2. Reproducible HTTP evidence

Test environment: Windows, PowerShell 5.1, `curl.exe` (Windows build), Python 3.12.4, `pypdf` (installed), `pdftotext` 23.13.0 for independent cross-checks. All requests used HTTPS and a descriptive User-Agent. Sanitized commands are in section 11.

| Endpoint | Test time (UTC) | Request (sanitized) | Status / Content-Type | Observed shape | Conclusion |
|---|---|---|---|---|---|
| `/` | 22:04:25Z | `GET /` | 200 `text/html; charset=UTF-8`; 50,466 B; `PHPSESSID`; `Cache-Control: no-store` | Portal HTML with inline jQuery; 10 recent bulletin dates, latest `2026-11-13`; XHR code calls `mapa`, `analisesPonto`, catalog, CSV, HTML and PDF routes | Index is the discovery source for the latest bulletin date. No static API docs. |
| `/municipio/getMunicipios` | 22:04:38Z | `POST` empty body | 200 `text/html; charset=UTF-8`; 1,657 B | JSON array of 28 `{"CODIGO": "Araranguá", "DESCRICAO": "Araranguá"}`; `CODIGO` is the **name**, not a numeric ID | Catalog is name-keyed. GET also returned the same body, but POST is the portal behavior. |
| `/local/getLocaisByMunicipio` | 22:04:39Z | `POST municipioID=Porto Belo` (and Garopaba, Itapoá, Bombinhas, Florianópolis) | 200 `text/html; charset=UTF-8` | JSON array: `CODIGO`, `BALNEARIO`, `MUNICIPIO`, `LATITUDE`, `LONGITUDE`; `CODIGO` is the beach name. Porto Belo = 2, Garopaba = 4, Itapoá = 3, Bombinhas = 10 beaches | Municipality is a required name; `municipioID=0` returns the literal body `null` (not "all"). |
| `/pontoColeta/getPontosByLocal` | 22:04:52Z approx. | `POST localID=Praia de Perequê` (and others) | 200 `text/html; charset=UTF-8` | JSON array: UUID `CODIGO`, `NOME` ("Ponto 03"), `OCULTAR`, `LOCAL_ID`, `LOCALIZACAO`, `LATITUDE`, `LONGITUDE`, `CONDICAO` | Point UUID is the stable key. `localID=0` returns `null`. Perequê has 3 points; Garopaba 2; Itapoá main beach 4. |
| `/registro/anosAnalisados` | 22:04:39Z | `POST` empty body | 200 `text/html; charset=UTF-8`; 361 B | 24 objects `{"ANO":"2026"}` … `{"ANO":"2003"}` | Year coverage claim is 2003–2026. It does not guarantee data for every beach/year. |
| `/relatorio/mapa` | 22:04:40Z | `POST` empty body | 200 `text/html; charset=UTF-8`; 85,280 B | 260 objects; keys `CODIGO` (UUID), `MUNICIPIO_COD_IBGE`, `MUNICIPIO`, `PONTO_NOME`, `BALNEARIO`, `LOCALIZACAO`, `LATITUDE`, `LONGITUDE`, `CONDICAO`; 208 `PRÓPRIO`, 52 `IMPRÓPRIO`; **no `ANALISES`, no date** | Point registry and undated current snapshot only. GET returned the same body; HEAD timed out at 30 s. |
| `/relatorio/analisesPonto` | 22:04:52Z | `POST codigo=<point UUID>` | 200 `application/json`; 533 B for one point | Array of 5 dated objects: `DATA` `dd/mm/yyyy`, `CONDICAO` (`PRÓPRIO`/`IMPRÓPRIO`), `CHUVA`, `RESULTADO` (string, e.g. `"373"`), `TEMP_AGUA` (string, e.g. `"21.00"`) | Undocumented, portal-internal, but the best cheap dated point source. Invalid UUID → `[]` (200); missing `codigo` → **500 HTML with a PHP stack trace**. |
| `/relatorio/exportarCSV` | 22:05:20Z | `POST municipioID=Porto Belo&localID=Praia de Perequê&ano=2026` | 200 `text/csv; charset=UTF-8`; `Content-Disposition: attachment`; 12,399 B; dynamic filename | UTF-8 BOM, LF, 13 columns, 75 data rows; dates `dd/MM/yyyy`, times `HH:mm`; conditions `PRÓPRIA`/`IMPRÓPRIA`; `<20`/`<10`/`> 24196` forms; no point UUID or coordinates | Primary history source. Municipality/beach are names. Unknown local → 137-byte header-only file. Missing year → per-point `Sem registros` rows, not an error. GET ignores query fields and returns 260 `Sem registros` rows. |
| `/relatorio/historico` | 22:05:40Z | `POST municipioID=Porto Belo&localID=Praia de Perequê&ano=2026&redirect=true` | 200 `text/html; charset=UTF-8`; 76,431 B | Full HTML page; table is for the selected point, with Data/Hora/Vento/Maré/Chuva/Água/Ar/E. coli/Condição | Same data as CSV but harder to parse and per-point. Not recommended as the primary history path. |
| `/relatorio/downloadPDF/2026-11-13` | 22:05:38Z | `GET` | 200 `application/pdf`; 317,885 B; `inline; filename="relatorio_n53-2026.pdf"` | 19 pages; report 53/2026; `DATA: 13/11/2026`; samples `09, 10 e 11 de novembro de 2026`; 260 point rows; 257 in the collection window, 3 carried forward; footnote excludes Pontos 83, 94 and 96 in Florianópolis | Authoritative published bulletin. Latest date discovered from the index. Unknown PDF date → 404 HTML. |
| `/relatorio/downloadPDF/2026-11-12` | 22:06Z approx. | `GET` | 404 `text/html` | CodeIgniter 404 page | Not every calendar date is a bulletin. Discover dates from the index. |

### 2.1 HTTP behavior that affects the adapter

- `http://balneabilidade.ima.sc.gov.br/` → **301** to HTTPS. Use HTTPS only.
- JSON catalog/map endpoints return `text/html; charset=UTF-8` even though the body is JSON. `analisesPonto` returns `application/json`. **Parse by body, validate the shape, and do not trust Content-Type alone.**
- `Cache-Control: no-store, no-cache, must-revalidate` on catalog/map/CSV; PDF is `Cache-Control: private`. The server sets `PHPSESSID` but does not require it for these requests.
- No `Access-Control-Allow-Origin` with an `Origin` header; `OPTIONS /relatorio/mapa` timed out after 20 s. Browser-side direct calls are not viable; a server-side MCP is required.
- No rate-limit or retry headers observed (`X-RateLimit-*`, `Retry-After` absent). Absence is not permission to poll aggressively.
- `HEAD /relatorio/mapa` timed out after 30 s with no bytes. Use POST/GET, not HEAD.
- `robots.txt` is **404**; there is no crawl policy to read. Treat the portal as a public service, keep volumes low, cache, and identify the client.

## 3. Catalog shape and counts

Live snapshot (2026-11-14T22:04:40Z):

- **260 points**, **28 municipalities**, **139 distinct beach names**, **88 distinct point names** (`Ponto 01` … `Ponto 98` with gaps).
- Conditions: **208 `PRÓPRIO`**, **52 `IMPRÓPRIO`**, **0 `INDETERMINADO`** in this snapshot. The UI and historical data model still need the indeterminate state.
- Municipality catalog: 28 names, no numeric ID. `MUNICIPIO_COD_IBGE` exists only on map points.
- Beach catalog: `CODIGO` is the beach **name**; no independent beach UUID.
- Point catalog: UUID `CODIGO`; `OCULTAR` flag exists, all sampled points seen were `N`.
- Point counts per beach range from 1 to 10 (e.g. Praia Central / Balneário Camboriú = 10; Lagoa da Conceição = 9; Praia dos Ingleses = 8; Itapema = 8).
- **97 beaches have a single point**, so a point verdict is often the whole beach — but not always. Do not generalize without checking.

The Marola issue reported **337 points** on 2026-10-06; the current live count is **260**, and bulletin 53 says 260. Point counts change (season, network adjustments, hidden points), so cache the catalog but refresh it, and never hard-code counts or point numbers.

## 4. Endpoint semantics in detail

### 4.1 `/relatorio/mapa` — catalog + undated snapshot

Representative object (one point, public data; escaped accents shown as returned):

```json
{"CODIGO":"390f41d4-e7d0-4642-baf4-b6ae2ceb111a","MUNICIPIO_COD_IBGE":"4213500","MUNICIPIO":"Porto Belo","PONTO_NOME":"Ponto 03","BALNEARIO":"Praia de Perequê","LOCALIZACAO":"Avenida Senador Atílio Fontana, n°266, foz do Rio Perequizinho","LATITUDE":"-27.15552490","LONGITUDE":"-48.56434520","CONDICAO":"PRÓPRIO"}
```

- `CODIGO` is a UUID and is the only stable point key exposed by the portal.
- Coordinates are strings with 8 decimal places; parse as decimal/float with a range check.
- `CONDICAO` is **undated**. It matched the latest PDF row for all 260 points, but for 3 points that latest row is not current-valid (section 6). It must not be used as "status today".
- No `ANALISES` in any of the 260 objects. Marola's `ImaScWaterQualityClient` expects `ANALISES` and therefore yields no points from this shape; its PDF fallback is the consequence documented in issue #57.

### 4.2 `/relatorio/analisesPonto` — last five dated analyses

Representative response for Perequê Ponto 03 (2026-11-14):

```json
[
  {"DATA":"09/11/2026","CONDICAO":"PRÓPRIO","CHUVA":"Ausente","RESULTADO":"373","TEMP_AGUA":"21.00"},
  {"DATA":"03/11/2026","CONDICAO":"PRÓPRIO","CHUVA":"Ausente","RESULTADO":"616","TEMP_AGUA":"25.00"},
  {"DATA":"26/10/2026","CONDICAO":"PRÓPRIO","CHUVA":"Moderada","RESULTADO":"677","TEMP_AGUA":"21.00"}
]
```

- Exactly 5 rows for every valid point tested (22 points across Porto Belo, Garopaba, Itapoá, Bombinhas and the three Florianópolis carry-forward points).
- `DATA` is the **sample date**, not the bulletin date. CSVs and PDFs use the same dates for the same samples.
- `CONDICAO` is the IMA/SC rolling classification (masculine `PRÓPRIO`/`IMPRÓPRIO`); `RESULTADO` is the E. coli count as a string and may be a qualifier in CSV but was numeric in the JSON rows inspected.
- It includes the **discarded** Ponto 83 sample (05/11/2026), so it is not by itself proof of what the latest bulletin published.
- Invalid UUID → `[]`; missing `codigo` → 500 HTML with a stack trace that leaks server paths. Validate the UUID and never request without one.

### 4.3 CSV export — history and lab values

Observed header (exact, including the typo in the temperature columns):

```text
Municipio,Balneario,"Ponto Coleta",Localização,Data,Hora,Vento,Maré,Chuva,"Água (ºC}","Ar (ºC}","E. coli NMP*/100ml",Condição
```

Representative rows:

```text
"Porto Belo","Praia de Perequê","Ponto 03","Avenida Senador Atílio Fontana, n°266, foz do Rio Perequizinho",09/11/2026,10:00,Sudeste,Enchente,Ausente,21,20,373,PRÓPRIA
"Florianópolis","Praia do Campeche","Ponto 35","Em frente à Avenida Pequeno Príncipe, n°3348",15/12/2003,09:37,Nordeste,Vazante,Moderada,21,27,<20,PRÓPRIA
"Florianópolis","Praia do Campeche","Ponto 90",2003,"Sem registros"
```

Confirmed semantics:

| Property | Observation |
|---|---|
| Method/fields | `POST` form fields `municipioID` (name), `localID` (beach name), `ano` (4-digit year). Names, not numeric IDs. |
| Content | `text/csv; charset=UTF-8`, UTF-8 BOM `EF BB BF`, LF line endings, `Content-Disposition: attachment` with a timestamped filename. |
| Columns | 13; the header was identical in the years checked (2003, 2010, 2024–2026), including the `}` typo in `Água (ºC}`/`Ar (ºC}`. Match tolerantly, preferably by position. |
| Dates/times | `Data` = `dd/MM/yyyy` (sample date); `Hora` = `HH:mm`, local time, no timezone marker. |
| Conditions | `PRÓPRIA`/`IMPRÓPRIA` (feminine), unlike the JSON's masculine `PRÓPRIO`/`IMPRÓPRIO`. Normalize by prefix, do not compare labels literally. |
| E. coli | Integer, or censored/qualified `<20`, `<10`, `> 24196`, `>24196` (space variant). Unit column says `NMP*/100ml`. Preserve the qualifier; do not turn `<20` into exactly 20. |
| Missing values | Empty strings occur (e.g. 2003 temperatures). `Sem registros` rows are short (5 fields), with the year in `Data` and the marker in the last field. |
| Empty results | Unknown `localID` or a beach/municipality mismatch → 200 with **header only** (137 B). Missing year → 200 with one `Sem registros` row per point (e.g. 320 B for 3 points). These are data states, not HTTP errors. |
| Ordering | Grouped contiguously by point, descending date within each point. Do not assume a global date sort. |
| Coverage | 2003–2026; per-beach coverage varies. Campeche 2003 had 27 real rows plus 4 `Sem registros` rows; Campeche 1999 had 5 `Sem registros` rows. |
| Identity | No point UUID, no coordinates. Join on (`Municipio`, `Balneario`, `Ponto Coleta`). This key matched 100% of rows for the four municipalities tested. |
| Method trap | `GET /relatorio/exportarCSV` (even with query fields) returned 260 `Sem registros` rows and ignored the supplied parameters. Use POST with form fields. |

**Fixture reproducibility:** the live Campeche 2003 CSV (4,559 B) is byte-identical (SHA-256 `93EBD0CC…F28B7`) to Marola's `campeche-2003.csv` fixture. The 137-byte header-only result matches Marola's `header-only.csv` size. The 1999 fixture has the same 472-byte size and five-row `Sem registros` shape as the live 1999 output. This gives high confidence in the CSV contract.

### 4.4 PDF bulletin — authoritative dated publication

- Latest index link: `2026-11-13`; PDF filename `relatorio_n53-2026.pdf`; 317,885 B; SHA-256 `4DB43C6C…A2347A`.
- Report **53/2026**, `DATA: 13/11/2026`; collection described as **09, 10 and 11 November 2026**; 19 pages.
- Table columns: `BALNEÁRIO / LOCAL DE COLETA`, `DATA DA COLETA`, `CONDIÇÃO`. Address lines follow the point heading. No E. coli counts or coordinates.
- 260 point rows parsed. 257 have a sample date in the stated collection window; 3 are carried or excluded: Ponto 83 (05/11/2026, discarded), Ponto 94 (19/10/2026, not collected), Ponto 96 (26/05/2026, not collected). The footnote is explicit:

```text
* Pontos 94 e 96 em Florianópolis não foram coletados por falta de acesso.
* Ponto 83 em Florianópolis teve problemas no transporte e foi descartada.
```

- The map `CONDICAO` matched the PDF row condition **260/260**. The map is therefore a *consistent but undated* snapshot, not a validity filter.
- Parsing feasibility: with the system pypdf 6.16.2 used during the initial investigation, page 19 (complementary information: recommendations, methodology, CONAMA 274 classification) raised `PdfReadError` on a malformed content stream. The pinned provider version 6.21.4 extracted all 19 pages. Page-level tolerance remains necessary because PDFs vary, but the current point table is complete.
- Lookahead matters: on pypdf text, **73 of 260** headings have the date/verdict 3–7 lines later because the address wraps. A two-line window parsed only **187/260** rows; searching forward until the next heading (up to 8 lines) recovered **260/260**. Marola's `VerdictWithinLines=2` would be unsafe with this extraction.
- Two headings wrap across lines in the extracted text (`Lagoa Boca da Barra - Na foz do Canal do Linguado (Ponto` + `02)`; `Praia da Costeira da Armação- Baía dos Golfinhos (Ponto` + `03)`). A naive line parser misses them. With a two-line heading reflow, all 260 rows matched the catalog; without it, 258/260 matched. This is a concrete correctness risk, not a cosmetic one.
- An older bulletin (46/2026, 2026-09-24) also parsed to 260 rows but most sample dates were 25–28/08/2026, with 10 points collected on 21/09/2026 in Balneário Camboriú. The intro explains the **off-season monthly cadence** (April–September) and a court-ordered weekly exception for Balneário Camboriú. A PDF row can therefore be legitimately ~30 days old in the off-season. Freshness must be season-aware, not a single fixed number.

### 4.5 Historical HTML

`POST /relatorio/historico` with the same fields plus `redirect=true` returned a 76 KB HTML page for the selected point, with the same rows and values as the CSV. It is serviceable as a human page but not a good machine contract (HTML layout, per-point page, no stable schema). Keep it as a last-resort diagnostic, not a provider path.

### 4.6 Marola reference implementation (code inspection only)

Pinned commit `7061a08e643c5fe05485cb2917be405f5b1ab8c4`; MIT (copyright 2026 marola.dev). The code was read, not executed; no Marola behavior is claimed beyond what the code and issue say.

**What the code does**

- `ImaScWaterQualityClient`: `POST /relatorio/mapa`, empty form; parses `CODIGO`, `BALNEARIO`, `PONTO_NOME`, `LOCALIZACAO`, coordinates and `ANALISES`; drops points whose coordinates are missing or whose `ANALISES` list is empty; folds `PRÓPRIA/IMPRÓPRIA` accents/case into proper/improper; uses a **45-day** `isFresh` window (`WaterQuality.MaxSampleAgeDays`).
- `ImaScPdfWaterQualityClient`: discovers the newest `/relatorio/downloadPDF/<date>` link from the portal index (does not hard-code a bulletin), downloads the PDF, parses rows with PDFBox geometry (`PdfLines`), joins rows to the map points on folded `BALNEARIO|PONTO_NOME`, and drops points present in only one source. It uses HTTPS defaults after issue #57.
- `ImaScPdfParser`: expects a heading like `PRAIA DO ARROIO DO SILVA (Ponto 01)`, then a date+verdict within the next two lines; keeps the row's real date even when IMA carries an older sample forward (the test explicitly expects Ponto 96 at 26/05/2026).
- `FallbackWaterQualityClient`: primary JSON, then PDF when the primary returns no points or fails; `CachedWaterQualityClient`: serves the last non-empty cache with original dates, and refuses to overwrite a good cache with an empty fetch.

**Reusable conceptually**

- Dynamic bulletin-date discovery from the index.
- Accent/case folding and explicit raw-label preservation.
- Joining PDF rows to the JSON catalog and refusing to guess unmatched rows.
- Primary → fallback → cache ordering, with "empty is not success".
- Refusing to treat a point with no dated sample as a valid point.
- Geometry-aware PDF parsing (the PDF table is not readable in naive natural order).

**Limitations for our use case**

- Its primary JSON parser now yields nothing because the map has no `ANALISES`; the PDF fallback is mandatory, not optional.
- The join key omits municipality. The current snapshot has no beach+point collisions, but duplicate beach names exist across municipalities; we will include municipality.
- The 45-day freshness rule accepts Ponto 83 (05/11, discarded, 8 days) and Ponto 94 (19/10, not collected, 25 days). It does not parse the bulletin's exclusion footnote or collection window. We will add both.
- It drops rows it cannot match and logs a warning; for a safety product we will expose unmatched rows and degrade explicitly instead of silently dropping.
- It parses with PDFBox/Scala; our Python implementation needs `pypdf` (plus page-level tolerance and heading reflow) or an alternative, with fixtures from more than one bulletin.
- It has no CSV history adapter in `marola-app` at this commit; CSV is designed in MIP-0056 but not shipped. We cannot treat it as a tested CSV implementation.
- Its tests cover the 2026-09-05 map shape with `ANALISES` and a 2026-08-28 PDF, not the current 2026-11-13 PDF or the 3 carried/excluded points.

**MIT attribution obligations**

If we copy code (not just ideas), we must retain the MIT copyright notice and permission notice in the copied source/distribution, and identify marola.dev as the origin. Conceptual reuse should still be credited in the repository documentation. No Marola code is copied; the project code is MIT and the data license remains unresolved.

## 5. Source comparison

| Property | Map JSON | `analisesPonto` JSON | CSV export | Bulletin PDF | Historical HTML |
|---|---|---|---|---|---|
| Point identity | UUID | UUID input | Name tuple only | Name tuple only | Name tuple only |
| Coordinates | Yes | No | No | No | No |
| Dated samples | **No** | **Yes, last 5** | **Yes, full year** | **Yes, bulletin rows** | Yes, per point |
| Lab values | No | Yes (last 5) | Yes | No | Yes |
| Bulletin date | No | No | No | **Yes** | No |
| Exclusion/carry-forward context | No | No | No | **Yes (prose/footnote)** | No |
| Coverage | Current catalog | 5 most recent | 2003–2026, per beach/year | Current bulletin only | Selected point/year |
| Best use | Catalog/IDs/coords | Cross-check/fallback | History | **Latest published status** | Diagnostics |

Cross-checks performed:

- **Map vs bulletin:** 260/260 keys matched after accent/case/whitespace folding. Conditions matched 260/260. But 3 PDF rows are outside the current collection window and are explicitly excluded/carried forward.
- **CSV vs bulletin:** 0 date/condition differences for the latest row of **105 points** across 4 municipalities (Porto Belo 6, Garopaba 5, Itapoá 6, Florianópolis 88). This includes the 3 carry-forward points, where both sources agree on the old date and condition.
- **`analisesPonto` vs CSV:** 85 rows across 17 points in 3 municipalities, 0 semantic mismatches (after mapping `PRÓPRIO`/`PRÓPRIA` to proper/improper). The comparison caught the gender difference, not a data discrepancy.
- **PDF vs map condition:** 260/260 matches; therefore map condition is not independent evidence of freshness.

**Conclusion:** the sources are consistent about *what was measured and how it was classified*. They differ in *what is current*. The PDF is the only source that states the publication date and the exclusion context; CSV is the only full-history source with lab values; `analisesPonto` is the cheapest per-point dated check; the map is catalog-only.

## 6. Freshness, staleness and exclusions — the safety-critical finding

Bulletin 53 facts:

| Point | Beach / municipality | PDF sample date | PDF condition | Bulletin statement | Correct interpretation |
|---|---|---|---|---|---|
| Ponto 83 | Praia de Ponta das Canas / Florianópolis | 05/11/2026 | IMPRÓPRIA | sample discarded due to transport problems | **Not a valid current verdict.** 8 days old, so a 45-day rule would accept it. |
| Ponto 94 | Beira-Mar Norte / Florianópolis | 19/10/2026 | IMPRÓPRIA | not collected (access) | **Carried forward**, 25 days old at bulletin date. |
| Ponto 96 | Lagoa da Conceição / Florianópolis | 26/05/2026 | IMPRÓPRIA | not collected (access) | **Carried forward**, 172 days old. |

The bulletin prose says 257 points were monitored that week, while the table has 260 rows. The 3-row difference is exactly these carried/excluded points. This is the single most important reason not to present the map `CONDICAO` as "current".

A 45-day threshold (Marola's choice, reasonable for monthly off-season sampling) fails here: it accepts Ponto 83 (8 days) and Ponto 94 (25 days). The current bulletin is in-season (weekly), so the threshold must be tighter, and the bulletin's own exclusions must be honored.

### Freshness policy (implemented)

1. **Authoritative latest:** the newest bulletin PDF discovered from the portal index.
   - Parse `bulletin_date` from `DATA:`, report number, and the collection dates from the intro when present.
   - Parse point rows with heading reflow; validate row count against the catalog and against the bulletin's stated count; expose unmatched rows, never silently drop them.
   - Parse the footnote for excluded point numbers/municipality (conservative; if the footnote is unparseable, mark uncertainty).
2. **Per-point freshness flags:**
   - `current`: row date is within the expected cadence window and the point is not in an exclusion footnote.
   - `carried_forward`: row present but older than the cadence window; show the date and age, never call it current.
   - `excluded`: explicitly excluded/discarded in the bulletin.
   - `stale`: cached/older data outside the window.
   - `unverified`: no bulletin could be parsed; CSV/analyses used with a conservative age check.
   - `unknown`: no dated sample at all.
3. **Cadence thresholds (proposal, evidence-based):**
   - In-season (October–March, weekly): sample within **10 days** of the bulletin date; the three current-week dates are typically 2–4 days before publication.
   - Off-season (April–September, monthly): sample within **40 days**; bulletin 46 shows legitimate ~30-day-old rows.
   - These thresholds are **provisional**; further bulletins should test them across more bulletins. The PDF's stated collection dates and exclusion footnote take precedence over the numeric threshold.
4. **Fallback if PDF fails:** use the latest CSV row for the beach/year (fetch current year, then previous year), plus `analisesPonto` for the points. Set `bulletin_unverified=true`, `bulletin_date` from the cached index if known, and apply the same age window conservatively. Never upgrade an unverified result to `proper` beach summary.
5. **Never** use map `CONDICAO` as the status. If only the map is reachable, return `unknown` with catalog data and an explicit provider-degraded warning.
6. **Cache:** serve the last good bulletin/catalog with original dates; do not overwrite good cache with empty responses. Recompute ages at read time, not cache time.

### Beach summary rules

- Any `improper` point → summary is **not proper**; if proper and improper coexist → `mixed`.
- All points proper and all current → `proper` (still with sample/bulletin dates).
- Any missing/stale/excluded/unknown point and no improper → `partial` (or `unknown` if none valid), with counts.
- Any indeterminate → `mixed`/`indeterminate`; never proper.
- No valid points → `unknown`.
- Always include per-point details; never collapse to a single beach verdict without showing the point list.

## 7. Tested locations and failure cases

| Case | Evidence | Use in tests |
|---|---|---|
| Porto Belo / Praia de Perequê | 3 points (03, 04, 05); all `PRÓPRIO` on 09/11/2026; 75 CSV rows in 2026, latest 09/11 for all 3; 1 point (03) has 5 JSON analyses matching CSV. | Multi-point beach, all-proper, latest status. |
| Garopaba / Praia de Garopaba | 2 points (01, 02); both `PRÓPRIO` on 10/11/2026; 5 Garopaba beaches; 124 CSV rows in 2026. | Multi-point, all-proper, different sample day. |
| Itapoá / Praia de Itapoá | 4 points (01–04), all `PRÓPRIO` on 10/11/2026; separate beach `Praia de Itapoá - no rio` Ponto 05 is `IMPRÓPRIO`; 148 CSV rows in 2026. | Beach vs nearby river-mouth point; don't merge. |
| Bombinhas / Praia de Zimbros | Ponto 09 `IMPRÓPRIO` and Ponto 10 `PRÓPRIO`, both sampled 09/11/2026. Ponto 09 count 1046, Ponto 10 count 789. | **Mixed beach**; must not report whole beach proper. |
| Duplicate beach names | `Praia Brava` in Florianópolis (Pontos 24, 25, 69, 79) and Itajaí (03, 04, 05); also `Praia dos Ingleses` (Florianópolis / São Francisco do Sul), `Praia de São Miguel` (Biguaçu / Penha), `Praia Grande` (Gov. Celso Ramos / Penha). | Municipality qualifier; ambiguous search must return candidates. |
| Accents/case | Names include `Perequê`, `Garopaba`, `Itapoá`, `Conceição`, `Armação`; JSON, CSV and PDF use different casing/accents. | Fold NFD accents and case; preserve raw names. |
| No data | Unknown `localID` → 137-byte header only; missing year → `Sem registros` rows; 1999 Campeche → 5 `Sem registros` rows; invalid UUID → `[]`. | Return explicit no-data/unknown, never proper. |
| Stale/excluded | Pontos 83, 94, 96 in bulletin 53; old dates and footnote. | Staleness/exclusion regression tests. |
| Off-season cadence | Bulletin 46/2026-09-24: 260 rows, most dates 25–28/08/2026; 10 Balneário Camboriú points 21/09/2026; monthly cadence. | Season-aware freshness tests. |
| Point count drift | Marola issue #57 reported 337 points on 2026-10-06; live 260 on 2026-11-14; bulletin 53 says 260. | Do not hard-code counts/point numbers. |

No `INDETERMINADO` appeared in current map, CSV or PDF data. The enum must still exist because the portal UI handles it; unknown/indeterminate must never be silently mapped to proper.

## 8. Recommended architecture

### 8.1 Source precedence

```text
Latest published status:
  1. Latest bulletin PDF (dated row + collection window + exclusions)
  2. CSV latest row for beach/year + analisesPonto (bulletin unverified; conservative age)
  3. Last good cached bulletin (dates unchanged; recompute age)
  4. unknown / provider_degraded (never map CONDICAO as status)

History:
  1. CSV export by (municipality, beach, year)
  2. Cached CSV/bulletin records
  3. explicit no-data

Catalog:
  1. /relatorio/mapa (UUIDs, coordinates, names)
  2. cached catalog (TTL)
```

### 8.2 Components

- `ima/http`: `httpx.AsyncClient` with 20–30 s timeouts, bounded retries (2–3, exponential backoff, retry only 5xx/timeouts), descriptive User-Agent, HTTPS only, no HEAD, no browser spoofing. Parse bodies defensively; JSON endpoints may claim `text/html`.
- `ima/catalog`: municipalities → beaches → points; UUID, names, coordinates, `OCULTAR`; normalized keys (`municipality|beach`), accent/case folding, raw values preserved. TTL 24 h; stale cache allowed with `catalog_age`.
- `ima/bulletin`: index discovery (regex `/relatorio/downloadPDF/\d{4}-\d{2}-\d{2}`, choose max), PDF download by date (cache immutable), `pypdf` extraction with per-page error tolerance, heading reflow, row validation, bulletin date/report/collection window/footnote parsing, exclusion list, row-to-catalog join.
- `ima/history`: CSV POST by names/year, `utf-8-sig`, positional/tolerant header, `Sem registros` handling, qualifier parser (`<`, `>`), date/time parsing, join to catalog, year coverage.
- `ima/latest`: reconciliation of bulletin rows + CSV/analyses values, freshness flags, beach summary, per-point output, provenance.
- `models`: typed dataclasses/Pydantic models; enums for classification (`proper`, `improper`, `indeterminate`, `unknown`), freshness, source.
- `service`: use cases (`search_beaches`, `get_sampling_points`, `get_bathing_status`, `get_bathing_history`); no HTTP in tools.
- `mcp`: Python MCP SDK (`MCPServer` v2) over stdio; logs to stderr only; typed errors.

### 8.3 Join strategy

- Canonical point key: catalog UUID `CODIGO`.
- CSV/PDF key: normalized (`MUNICIPIO`, `BALNEARIO`, `PONTO_NOME`) → UUID. Always include municipality. The current snapshot has no 2-key collisions, but that is not a contract; duplicate beach names exist across municipalities and point names repeat (88 distinct names / 260 points).
- Normalize with Unicode NFD, strip combining marks, collapse whitespace, uppercase; preserve raw strings in output. Handle punctuation/spacing differences (e.g., `Armação-`, `n°`).
- If a row cannot be joined, expose it as `unmatched` (do not drop silently); if a catalog point has no row, mark `missing_from_bulletin`.
- PDF heading reflow: join a line ending in `(Ponto` with the next line if it begins with digits and `)`; then search the date/verdict forward until the next heading (observed up to 7 lines), not a fixed 2-line window. Validate the row count/key match against the catalog before trusting the parse.

### 8.4 Caching proposal

| Resource | Key | TTL / policy |
|---|---|---|
| Catalog/map | singleton | 24 h; serve stale with warning if refresh fails |
| Municipality/beach/point lists | municipality | 24 h; can be derived from map but these endpoints give names/locations |
| Bulletin index | singleton | 1 h (or 6 h); always check before status |
| Bulletin PDF | bulletin date | immutable by date; cache indefinitely (content-addressed) |
| CSV | municipality + beach + year | past years: immutable/30 d; current year: 6–24 h |
| `analisesPonto` | point UUID | 1–6 h; used as cross-check/fallback |
| Latest status response | query key | 1 h or until next bulletin; include `fetched_at` and ages |

No database needed for MVP. A small on-disk cache (JSON/binary keyed by hash) is enough. Never overwrite a good cache with an empty/partial fetch.

### 8.5 Error taxonomy

- `provider_unavailable` (timeout/5xx/DNS/TLS) vs `provider_schema_changed` (missing expected keys, PDF row count/key mismatch) vs `no_data` (valid empty result) vs `ambiguous_query` vs `invalid_argument`.
- Do not surface raw 500 HTML/stack traces; log sanitized details to stderr. Validate UUIDs, years (2003–current), municipality/beach names before requests.
- Partial results: return valid points with `warnings` and `partial=true`; never fabricate a missing point.

## 9. Legal, licensing and operational notes

- **No license/terms found.** The portal has no license/terms/open-data statement; `robots.txt` is 404; the Santa Catarina CKAN API search for `balneabilidade` returned **0 datasets**; Marola MIP-0056 independently records that IMA never published a license (verified on the portal and `dados.sc.gov.br`). Public availability is not a reuse license.
- **Do not commit IMA datasets or PDFs.** The repository should contain code, docs and small synthetic/derived fixtures only. Fetch at runtime, attribute IMA/SC, and decide a data-reuse policy before publishing cached datasets. Project code is MIT; the IMA data-reuse license remains unresolved.
- **Attribution:** cite `Instituto do Meio Ambiente de Santa Catarina (IMA/SC)` and the portal URL in every response; include the bulletin/report number and source URL where available.
- **Politeness:** low request volume, caching, timeouts, bounded retries, backoff on 5xx, no parallel hammering, no scraping of all 260 points when one PDF covers them. Avoid `OPTIONS`/HEAD probes in production.
- **CORS:** not available; a browser-only client cannot call IMA directly. Server-side MCP avoids this. Do not add a public proxy without auth/abuse controls.
- **Transport:** HTTPS only (HTTP 301). The host previously had certificate/availability incidents (Marola issue #57, MIP-0056); build fallback/caching for outages.
- **Timezone:** sample dates are local dates (`America/Sao_Paulo`); do not shift them. Store dates as calendar dates, not instants. `fetched_at` in UTC.
- **Security:** the portal leaks a PHP stack trace on missing `codigo`; never echo upstream error bodies. Treat all upstream text as untrusted; no HTML rendering.

## 10. Risks and confidence

| Risk | Evidence | Mitigation | Confidence |
|---|---|---|---|
| Undocumented API changes | `ANALISES` removed; point count 337 → 260; `analisesPonto` undocumented | Shape validation, schema-change errors, PDF/CSV fallback, fixtures | High |
| PDF parsing fragility | Page 19 `PdfReadError`; 2 wrapped headings; font/encoding differences; carried rows | Per-page tolerance, heading reflow, row/key/count validation, alternate extractor, expose partial | High |
| Stale/discarded verdict presented as current | Ponto 83 8 days old but discarded; 94/96 carried | Bulletin exclusion footnote + season-aware age + explicit freshness flags; never map CONDICAO | High |
| Name-based joins | CSV/PDF have no UUID; 88 point names for 260 points; duplicate beach names | Use (municipality, beach, point), normalize accents, expose unmatched; validate uniqueness per snapshot | High |
| No license | No terms, robots 404, CKAN 0; MIP-0056 says no license | Don't redistribute data; attribute; decide policy before caching/publishing datasets | High |
| CORS/remote misuse | No ACAO; OPTIONS timeout | Server-side stdio MCP; no public proxy without auth | High |
| Rate limiting unknown | No rate headers; no robots | Cache, low volume, backoff, no load tests | Medium |
| Seasonality/cadence | Off-season monthly; in-season weekly; court-ordered exception | Season-aware thresholds + bulletin collection dates | High |
| Point count/network drift | 337 vs 260; hidden/retired points possible | Refresh catalog, don't hard-code, expose unmatched | High |
| Timezone/date ambiguity | Dates lack timezone; local dates | Calendar dates in `America/Sao_Paulo`; no UTC conversion | High |

Overall discovery confidence: **high** for endpoint behavior, CSV/PDF contracts, cross-source consistency, and the stale-point failure mode; **medium** for long-term API stability and for exact season-aware thresholds (need more bulletins); **unresolved** for data licensing and the project's own license.

## 11. Reproduction commands

Use HTTPS, a descriptive User-Agent, and `--data-urlencode` for accents. These are read-only and modest.

```bash
BASE=https://balneabilidade.ima.sc.gov.br
UA='balneabilidade-sc-mcp-discovery/0.1 (research)'

curl -sS -A "$UA" "$BASE/" -o portal.html
curl -sS -A "$UA" -X POST "$BASE/municipio/getMunicipios"
curl -sS -A "$UA" -X POST --data-urlencode 'municipioID=Porto Belo' "$BASE/local/getLocaisByMunicipio"
curl -sS -A "$UA" -X POST --data-urlencode 'localID=Praia de Perequê' "$BASE/pontoColeta/getPontosByLocal"
curl -sS -A "$UA" -X POST "$BASE/registro/anosAnalisados"
curl -sS -A "$UA" -X POST "$BASE/relatorio/mapa" -o mapa.json

# Dated per-point analyses (UUID from mapa.json)
curl -sS -A "$UA" -X POST --data-urlencode 'codigo=390f41d4-e7d0-4642-baf4-b6ae2ceb111a' \
  "$BASE/relatorio/analisesPonto"

# CSV history (POST; names, not IDs)
curl -sS -A "$UA" -X POST \
  --data-urlencode 'municipioID=Porto Belo' \
  --data-urlencode 'localID=Praia de Perequê' \
  --data-urlencode 'ano=2026' \
  "$BASE/relatorio/exportarCSV" -o pereque-2026.csv

# Latest bulletin date and PDF
curl -sS -A "$UA" "$BASE/" | grep -oE '/relatorio/downloadPDF/[0-9]{4}-[0-9]{2}-[0-9]{2}' | sort -u | tail -1
curl -sS -A "$UA" "$BASE/relatorio/downloadPDF/2026-11-13" -o boletim.pdf
```

Minimal response-shape checks:

```bash
# 260 points, no ANALISES, undated CONDICAO
jq 'length, (map(has("ANALISES")) | any), (.[0] | keys)' mapa.json

# CSV: BOM + header + 13 columns
xxd -l 16 pereque-2026.csv
head -1 pereque-2026.csv
```

**Validated reproduction artifact:** `python scripts/discovery_probe.py` performs a small read-only subset of these calls and checks the catalog, dated analyses, CSV and latest PDF shapes. It printed the expected 260 points, 5 analyses, 75 CSV rows and 317,885-byte PDF on 2026-11-14. It was re-run from a clean clone of commit `90c179f` and passed with the same counts. It is discovery tooling, not the MCP provider, and is not called by CI.

The full PDF parsing check (Python 3.12 + `pypdf`): extract pages 1–18, reflow headings, and assert the row count/key match against the catalog. The ad hoc scripts used for the deeper comparisons were discovery-only and were kept out of the repository (see `.gitignore`); the provider now implements these checks as offline tests.

## 12. Decision record

**Recommended routes and reasons**

- **Latest status:** bulletin PDF (authority, dates, exclusions) + CSV (lab values) + `analisesPonto` (cross-check). This is the only combination that can distinguish "old but published monthly result" from "carried-forward/excluded result".
- **History:** CSV by municipality + beach + year, joined to catalog by names, with UUIDs from the map.
- **Catalog:** `relatorio/mapa` plus `getLocaisByMunicipio`/`getPontosByLocal`; cache.
- **Map `CONDICAO`:** catalog/display metadata only; never a status source.

**Alternatives rejected**

- Map JSON as latest status: rejected — undated and accepts discarded/carried points (Ponto 83).
- `analisesPonto` as sole latest source: rejected — no bulletin date/exclusion context; includes discarded samples.
- CSV as sole latest source: rejected — no bulletin date/exclusions; requires year choice; no coordinates/UUID.
- PDF as sole source: rejected — no E. coli values/coordinates; parsing fragility; use CSV/catalog for those.
- Historical HTML: rejected as primary — per-point HTML, no stable schema.

**SDK/runtime and transport:** Python 3.12.4 with uv 0.11.28, `httpx` 0.28.1, `pypdf` 6.21.4, `tzdata`, typed dataclasses, `pytest` 8.4.2, `ruff` 0.17.5 and `mypy` 1.20.2. MCP Python SDK **2.3.0** was verified to expose `mcp.server.MCPServer`; it is an optional `mcp` extra over **stdio**. No remote MCP is implemented.

**Remaining open questions**

- Exact license/reuse policy for IMA data (do not publish datasets until decided).
- Project code is MIT (see LICENSE); IMA data-reuse licensing remains unresolved.
- Season-aware threshold calibration across more bulletins.
- Whether the IMA point UUID is stable long-term; monitor.
- Rate limits/abuse policy for any future remote deployment (not authorized now).

**Repository/publication evidence**

- Public repo: <https://github.com/LucioB16/balneabilidade-sc-mcp> (verified `visibility=PUBLIC`, `isPrivate=false`, default branch `main`).
- Initial commit: `d1b42a4052e7eefc62d68fe4e5b77731abd83286`; `git ls-remote origin` matched `refs/heads/main`.
- Initial docs commit SHA is recorded in Git history and on GitHub.

## 13. Implementation status

The normalized provider is implemented in `src/balneabilidade_sc_mcp/` and documented in [`PROVIDER.md`](PROVIDER.md). It parses the live 2026-11-13 PDF to 260 rows, distinguishes discarded Ponto 83 from carried Pontos 94/96, enriches samples with CSV values, and keeps the map out of the status path. Offline tests use synthetic fixtures and never call IMA.

The local stdio MCP server is documented in [`MCP_SERVER.md`](MCP_SERVER.md). Its deterministic parser remains primary; if the point table is incomplete, it returns `vision_fallback` metadata and `get_bulletin_page` renders the original PDF page as PNG for a vision-capable client. The server does not call an LLM and never fabricates missing rows.

History supports: `get_bathing_history`: inclusive year boundaries, descending order, bounded cursor pagination, raw CSV provenance, E. coli unit/qualifiers, exact-duplicate deduplication, separate `years_without_data`/`years_unavailable`, and `unmatched_names` for point-name drift. Live checks covered 2025 (3 points, 29/12/2025) and 2026 (latest bulletin 13/11/2026, 3 proper points).
