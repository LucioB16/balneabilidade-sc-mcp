#!/usr/bin/env python3
"""Read-only IMA/SC connectivity probe for discovery and diagnostics.

This is discovery tooling, not the MCP provider. It performs a handful of
requests against the public portal, prints small shape/count summaries, and
exits non-zero if a basic expectation fails. It never dumps a full dataset.

Usage:
    python scripts/discovery_probe.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.parse
import urllib.request

BASE = "https://balneabilidade.ima.sc.gov.br"
USER_AGENT = "balneabilidade-sc-mcp-discovery/0.1 (research; read-only)"
TIMEOUT = 30


def fetch(path: str, form: dict[str, str] | None = None) -> tuple[int, str, bytes]:
    """POST a form when *form* is given (including an empty form), else GET."""
    data = urllib.parse.urlencode(form).encode("utf-8") if form is not None else None
    method = "POST" if form is not None else "GET"
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read()


def as_json(body: bytes):
    return json.loads(body.decode("utf-8"))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    failures: list[str] = []

    status, content_type, body = fetch("/")
    dates = sorted(set(re.findall(rb"/relatorio/downloadPDF/(\d{4}-\d{2}-\d{2})", body)))
    latest = dates[-1].decode() if dates else None
    print(f"portal: HTTP {status} {content_type} bytes={len(body)} bulletins={len(dates)} latest={latest}")
    if status != 200 or latest is None:
        failures.append("portal index did not expose a bulletin date")

    status, content_type, body = fetch("/municipio/getMunicipios", {})
    municipalities = as_json(body)
    print(
        f"municipalities: HTTP {status} {content_type} count={len(municipalities)} first={municipalities[0]['DESCRICAO']!r}"
    )
    if not municipalities or not isinstance(municipalities[0].get("CODIGO"), str):
        failures.append("municipality catalog shape changed")

    status, content_type, body = fetch("/relatorio/mapa", {})
    points = as_json(body)
    has_analyses = any("ANALISES" in point for point in points)
    print(
        f"map: HTTP {status} {content_type} points={len(points)} "
        f"municipalities={len({p['MUNICIPIO'] for p in points})} "
        f"has_ANALISES={has_analyses} undated_CONDICAO={all('DATA' not in p for p in points)}"
    )
    if not points or has_analyses:
        failures.append("map shape is not the expected undated catalog")

    status, content_type, body = fetch("/local/getLocaisByMunicipio", {"municipioID": "Porto Belo"})
    beaches = as_json(body)
    print(
        f"beaches: HTTP {status} {content_type} Porto Belo count={len(beaches)} names={[b['BALNEARIO'] for b in beaches]}"
    )
    if not beaches:
        failures.append("Porto Belo beach catalog was empty")

    status, content_type, body = fetch("/pontoColeta/getPontosByLocal", {"localID": "Praia de Perequê"})
    beach_points = as_json(body)
    print(
        f"points: HTTP {status} {content_type} Perequê count={len(beach_points)} names={[p['NOME'] for p in beach_points]}"
    )
    if not beach_points:
        failures.append("Perequê point catalog was empty")

    point = beach_points[0]
    status, content_type, body = fetch("/relatorio/analisesPonto", {"codigo": point["CODIGO"]})
    analyses = as_json(body)
    print(
        f"analyses: HTTP {status} {content_type} point={point['NOME']} "
        f"rows={len(analyses)} latest={(analyses[0]['DATA'], analyses[0]['CONDICAO']) if analyses else None}"
    )
    if not analyses or "DATA" not in analyses[0]:
        failures.append("point analyses did not return dated rows")

    status, content_type, body = fetch(
        "/relatorio/exportarCSV",
        {
            "municipioID": "Porto Belo",
            "localID": "Praia de Perequê",
            "ano": "2026",
        },
    )
    text = body.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0] if rows else []
    data_rows = [row for row in rows[1:] if len(row) >= 13]
    has_bom = body.startswith(b"\xef\xbb\xbf")
    print(
        f"csv: HTTP {status} {content_type} bytes={len(body)} bom={has_bom} "
        f"columns={len(header)} rows={len(data_rows)} first_date={data_rows[0][4] if data_rows else None}"
    )
    if status != 200 or len(header) != 13 or not data_rows:
        failures.append("CSV export shape changed")

    status, content_type, body = fetch(f"/relatorio/downloadPDF/{latest}")
    print(f"bulletin: HTTP {status} {content_type} bytes={len(body)} date={latest}")
    if status != 200 or "application/pdf" not in content_type:
        failures.append("bulletin PDF was not downloadable")

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print(
        "\nOK: catalog, dated analyses, CSV history and bulletin PDF are reachable and shaped as documented."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
