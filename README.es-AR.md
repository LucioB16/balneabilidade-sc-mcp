<p align="center">
  <sub><a href="README.md">English</a> · <strong>Español (AR)</strong> · <a href="README.pt-BR.md">Português (BR)</a></sub>
</p>

<p align="center">
  <img src="assets/brand/wave-mark.svg" width="64" alt="Marca de ola de Balneabilidade SC MCP">
</p>

# Balneabilidade SC MCP

<p align="center">
  <strong>Preguntale a tu agente cómo está el agua de la playa.</strong><br>
  Un servidor MCP local con muestras fechadas publicadas por IMA/SC, punto por punto.
</p>

<p align="center">
  <a href="#instalación">Instalación</a> ·
  <a href="#instalación-manual">Instalación manual</a> ·
  <a href="#herramientas">Herramientas</a> ·
  <a href="#qué-devuelve-una-respuesta">Respuesta</a>
</p>

<p align="center">
  <a href="https://github.com/LucioB16/balneabilidade-sc-mcp/actions/workflows/ci.yml"><img src="https://github.com/LucioB16/balneabilidade-sc-mcp/actions/workflows/ci.yml/badge.svg" alt="Estado de CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-0B6E99" alt="Licencia MIT"></a>
</p>

> **Muestras fechadas, no lecturas en vivo.** La tarjeta de abajo es un extracto real de una respuesta MCP de la última muestra publicada por IMA/SC. No es una captura de pantalla ni una medición tomada ahora. IMA/SC muestrea semanalmente en temporada y mensualmente fuera de temporada.

| Última muestra publicada | Praia de Zimbros · Bombinhas |
|:--|:--|
| Ponto 09 | `improper` · 1.046 NMP/100mL |
| Ponto 10 | `proper` · 789 NMP/100mL |
| Fecha de muestra | 2026-11-09 |
| Boletín | 2026-11-13 |
| Resumen de la playa | `mixed` — los puntos no coinciden |

La respuesta nombra cada punto de muestreo, la fecha en que se tomó la muestra y el boletín que la publicó. Una playa nunca se reduce al veredicto de un solo punto.

## Qué podés preguntar

- “¿Cuál es el último resultado publicado para Praia de Zimbros y de cuándo es la muestra?”
- “Mostrame cada punto de muestreo; ¿las condiciones son mixtas?”
- “Mostrame el historial de Praia de Zimbros de 2025, con fechas y valores de laboratorio.”
- “¿Qué playas se llaman Praia Brava?” — la respuesta devuelve candidatos, no adivina.

## Instalación

### Instalación con tu agente

Copiá este prompt en un agente de programación. Incluye el repositorio y la guía de instalación, así el agente no tiene que buscar ninguno de los dos.

```text
Instalá el servidor MCP Balneabilidade SC desde:
https://github.com/LucioB16/balneabilidade-sc-mcp

Guía de instalación:
https://github.com/LucioB16/balneabilidade-sc-mcp/blob/main/docs/MCP_SERVER.md

Hacelo localmente. No busques el proyecto ni la documentación en otro lado.

Requisitos:
- Cloná el repositorio en una carpeta que yo confirme.
- Usá uv: ejecutá `uv sync --extra dev` y `uv run pytest`.
- Registrá un servidor MCP stdio local llamado `balneabilidade-sc`:
  `uv --directory <ruta> run balneabilidade-sc-mcp`
- Si no podés editar la configuración de mi cliente MCP, mostrame el JSON exacto y dónde pegarlo.
- Verificá que el cliente liste las cinco herramientas y hacé una consulta para "Praia de Zimbros", municipio "Bombinhas".
- Mostrame la configuración y la salida de verificación.

No expongas el servidor a la red. Pedime confirmación antes de modificar archivos fuera del proyecto o configuración global. No instales globalmente. No commitees credenciales ni configuración local.
```

Si `uv` no está instalado, pedime confirmación antes de instalarlo. La instalación manual está abajo.

### Instalación manual

```bash
git clone https://github.com/LucioB16/balneabilidade-sc-mcp.git
cd balneabilidade-sc-mcp
uv sync --extra mcp
uv run balneabilidade-sc-mcp
```

El último comando inicia el servidor stdio y espera a un cliente. Los logs van a stderr; stdout transporta el protocolo MCP.

Agregalo a un cliente MCP con `uv --directory` (ajustá la ruta absoluta):

```json
{
  "mcpServers": {
    "balneabilidade-sc": {
      "command": "uv",
      "args": [
        "--directory",
        "/ruta/absoluta/a/balneabilidade-sc-mcp",
        "run",
        "balneabilidade-sc-mcp"
      ]
    }
  }
}
```

En Windows también funciona el ejecutable instalado:

```json
{
  "mcpServers": {
    "balneabilidade-sc": {
      "command": "C:\\ruta\\a\\balneabilidade-sc-mcp\\.venv\\Scripts\\balneabilidade-sc-mcp.exe",
      "args": []
    }
  }
}
```

## Herramientas

| Herramienta | Entradas principales | Qué devuelve |
|:--|:--|:--|
| `search_beaches` | `query`, `municipality` opcional, `limit` | Playas candidatas, municipio, cantidad de puntos y tipo de coincidencia |
| `get_sampling_points` | `beach`, `municipality` opcional | UUIDs de puntos, ubicaciones y coordenadas |
| `get_bathing_status` | `beach`, `municipality` opcional, `point_id` | Último resultado fechado por punto, resumen de playa, frescura y procedencia |
| `get_bathing_history` | `beach`, `municipality` opcional, `point_id`, `from_date`, `to_date`, `limit`, `cursor` | Registros CSV fechados con cualificadores, unidad, nombres crudos y cobertura |
| `get_bulletin_page` | `page`, `bulletin_date` opcional, `dpi` | Página PNG solo para el fallback de visión |

## Qué devuelve una respuesta

Cada resultado fechado por punto incluye:

| Campo | Significado |
|:--|:--|
| `classification` | `proper`, `improper`, `indeterminate` o `unknown` |
| `freshness` | `current`, `carried_forward`, `excluded`, `stale`, `unverified` o `unknown` |
| `sample_date` | Fecha en que se tomó la muestra |
| `bulletin_date` | Fecha del boletín que la publicó, cuando se conoce |
| `source` / `source_url` | `bulletin_pdf`, `csv`, `analyses`, `catalog` o `cache`, más la URL de origen |
| `summary.status` | `proper`, `improper`, `mixed`, `partial` o `unknown` |

Un punto que IMA/SC no recolectó, o cuya muestra fue descartada, no se presenta como actual. El punto conserva su etiqueta cruda y una marca explícita de frescura. Cualquier punto impropio impide que el resumen de la playa sea `proper`.

## Historial

`get_bathing_history` lee los CSV publicados por IMA/SC:

- rango `from_date`/`to_date` inclusivo y orden descendente;
- paginación acotada con cursor;
- nombres crudos de punto, ubicación y `csv_year`;
- valores de E. coli con cualificadores `<20`/`<10`/`> 24196` y unidad `NMP/100mL`;
- `years_without_data` separado de `years_unavailable`;
- las filas duplicadas exactas se deduplican y se cuentan;
- la deriva de nombres se expone en `unmatched_names`, no se adivina;
- si CSV y el último boletín discrepan sobre la misma muestra, se conserva el veredicto del boletín y se devuelve un warning.

El historial es CSV-native. El PDF del último boletín es autoritativo para el estado actual.

## Ejemplos

Español:

- “¿Cuál es el último resultado publicado para Praia de Zimbros, en Bombinhas?”
- “Mostrame cada punto de muestreo y el historial de 2025.”

Portugués:

- “Qual é o último resultado publicado para a Praia de Zimbros, em Bombinhas?”
- “Mostre o histórico de 2025 com as datas e os valores de E. coli.”

Una buena respuesta siempre da el punto, la fecha de muestra y la fecha del boletín. No dice “está segura ahora”.

## Fallback de visión

El parser determinista del PDF es la vía principal. Si no puede validar una tabla de puntos confiable, `get_bathing_status` incluye metadatos `vision_fallback`. Un cliente con un modelo que tenga visión puede llamar a `get_bulletin_page` y leer las páginas PNG originales. El servidor no llama a un LLM, no inventa filas y no mejora el estado porque un modelo pueda leer una página.

## Desarrollo

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv build
```

La suite offline tiene 71 tests y nunca llama a IMA. La sonda de descubrimiento es separada y de solo lectura:

```bash
python scripts/discovery_probe.py
```

CI ejecuta lint, format check, mypy, tests offline y build del paquete en Python 3.11 y 3.12. No necesita credenciales ni hace llamadas a IMA.

## Datos, atribución y licencia

La fuente es el **Instituto do Meio Ambiente de Santa Catarina (IMA/SC)**, <https://balneabilidade.ima.sc.gov.br/>. Citá siempre el organismo, el número de informe/boletín, la fecha de muestra y la URL de origen.

No se confirmó una licencia de reutilización para el material de IMA/SC. Este repositorio no redistribuye PDFs, exportaciones CSV ni datasets masivos; el proveedor los obtiene en runtime. Ver [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md) antes de publicar datos derivados.

El código y la documentación tienen licencia MIT. La licencia no cubre los datos de IMA/SC. Ver [LICENSE](LICENSE).

## Limitaciones

- El parseo del PDF depende del layout; el fallback de visión lo maneja el cliente, no es un OCR del servidor.
- El historial es CSV-native; el PDF es autoritativo solo para el último boletín.
- Los joins por nombre exacto exponen la deriva en vez de adivinarla; un punto renombrado puede aparecer como unmatched.
- Solo stdio local: sin transporte remoto, autenticación, control de acceso ni rate limiting. No lo expongas a internet sin una revisión de seguridad separada.
- Sin base de datos: se usa una caché TTL pequeña para catálogo, PDFs y CSV.
- Esto no es una garantía médica ni de seguridad.

## Documentación

- [Informe de descubrimiento](docs/DISCOVERY_REPORT.md)
- [Contrato de producto](docs/PRODUCT_CONTRACT.md)
- [Proveedor](docs/PROVIDER.md)
- [Servidor MCP](docs/MCP_SERVER.md)
- [Notas de release](docs/RELEASE.md)
- [Atribución y licencia de datos](docs/ATTRIBUTION.md)
- [Política de seguridad](SECURITY.md)

## Estructura del proyecto

```text
src/balneabilidade_sc_mcp/
  provider.py       reconciliación de fuentes, frescura, historial
  bulletin.py       índice del portal, parseo de PDF, exclusiones
  history.py        exportación y parseo de CSV
  catalog.py        catálogo del mapa y matching
  server.py         herramientas MCP stdio
  pdf_vision.py     renderizado PNG de fallback
docs/               descubrimiento, contrato, proveedor, servidor, release, atribución
tests/              71 tests offline con fixtures sintéticos
```
