# Natalidad MX

Plataforma web analítica y geoespacial para la **Tasa Bruta de Natalidad (TBN)**
de México: 32 entidades federativas a nivel nacional y **drill-down
municipal para cualquiera de las 32 entidades** (2,436 municipios,
carga perezosa por estado), serie 2010–2024.

## Arquitectura

```
SINAC microdatos ─┐
CONAPO población ─┼─► pipeline/ (Polars) ─► data/interim/*.parquet
AGEEML catálogos ─┤                           │
                  │                           ▼
                  │                  web/data/{tasas.parquet, *.json}
Marco Geo (TopoJSON)────────────────► web/data/{*.topojson, *.geojson}
                                              │
                                              ▼
                                    web/ — cliente estático
                                    MapLibre GL + Apache ECharts
```

- **`pipeline/`** — ETL Python/Polars. Homologa 3 esquemas distintos de
  columnas SINAC (2010–2016 por nombre, 2017–2019 abreviado, 2020–2024
  extendido), resuelve la residencia de la madre a CVEGEO vía el catálogo
  SaS→INEGI (crosswalk por nombre normalizado dentro de cada entidad),
  calcula TBN, media móvil trienal centrada, cohortes por edad materna y el
  flag de baja escala (P < 10,000).
- **`web/`** — cliente estático sin build: MapLibre GL (WebGL), ECharts,
  simple-statistics (Jenks), topojson-client. Datos pre-agregados
  `{cvegeo → {v:[nac,pob,tbn,tbs], c:{cohorte:[nac,tbn,tbs]}, f}}`
  indexados por año para consultas O(1).

## Datos y fuentes

| Flujo | Fuente | Cobertura |
|---|---|---|
| Nacimientos | SINAC / DGIS Secretaría de Salud (`sinac_{año}.zip`) | 2010–2024, ~28.9M eventos |
| Población | CONAPO proyecciones a mitad de año (municipio + entidad) | 2010–2030 |
| Geometrías | Marco Geoestadístico (TopoJSON simplificado, cuantizado) | 32 entidades / 2,436 municipios (Mayo 2021) |
| Catálogos | AGEEML (`gaia.inegi.org.mx/wscatgeo/v2`) + catálogos SaS | — |

**Cobertura:** SINAC capta partos atendidos en unidades de salud
(≈86–90% del registro civil ENR). La TBN aquí publicada es la
*institucional*; se documenta en el panel meta del cliente. Se eligió
SINAC por ofrecer la serie 2010–2024 completa y consistente.

## Reglas del pipeline (RF-01)

- **Año de ocurrencia, no de registro** — cada evento se asigna al año en
  `FECHA_NACIMIENTO` (mitiga registro extemporáneo, TC-01).
- **Residencia habitual de la madre** — la agregación usa
  `ENTIDAD/MUNICIPIO_RESIDENCIA`; extranjero y no-especificado van a un
  bucket de exclusión (exclusiones.parquet, TC-02).
- **CVEGEO zero-padded de 5 dígitos** — `cve_ent(2)+cve_mun(3)`; Jalisco 14 +
  municipio 46 → `14046` (TC-04).
- **TBN** = nacimientos / población mitad de año × 1,000 (RF-01.3).
- **TFR** (tasa global de fecundidad) = 5·Σ_g B_g/W_g sobre grupos quinquenales
  de mujeres 15–49; umbral de reemplazo 2.1. Estatal/nacional usa
  denominadores CONAPO reales por edad; el municipal **aproxima** W_g con la
  estructura de edad estatal escalada por población femenina municipal
  (CONAPO no publica edad a nivel municipal).
- **Suavizada trienal** — media móvil centrada de 3 años por unidad (RF-03.2).
- **Flag baja escala** — `poblacion < 10,000` (RF-03.1, TC-03).

## Ejecutar

```bash
# pipeline (requiere polars; datos crudos en data/raw/ y sources/ según
# las rutas de cada módulo)
python -m pipeline.run                 # flujo completo
python -m pipeline.run --solo ingest   # una etapa

# cliente
cd web && python -m http.server 8340   # → http://localhost:8340

# reporte PDF (requiere los payloads de web/data/)
python pipeline/reporte.py
google-chrome --headless=new --no-pdf-header-footer \
  --print-to-pdf=docs/reporte_natalidad_mx.pdf \
  docs/reporte_natalidad_mx.html
```

## Funcionalidad del cliente

- Coropletas nacional → municipal (cualquier estado, click para drill-down)
  con clasificación **Jenks, cuantiles, intervalos iguales, desviación
  estándar** y rampa Viridis (daltónico-segura).
- Tooltip: nombre + CVEGEO + métrica + nacimientos + población + percentil.
- Filtros: año (2010–2024), cohorte de edad materna (incl. adolescentes <20),
  métrica tasa/TFR/volumen, tasa suavizada trienal.
- Gráficas: serie temporal vs. promedio de referencia, histograma+KDE,
  dispersión TBN×población (log), ranking top/bottom-10.
- Alerta visual (contorno punteado ámbar) en municipios P<10,000.
- Exportación: `.csv`, `.parquet`, `.geojson` enriquecido, `.png` ~300 DPI,
  `.svg` vectorial por gráfica.

## Reporte

`docs/reporte_natalidad_mx.pdf` — resumen analítico imprimible (KPIs
nacionales, serie 2010–2024, tabla de las 32 entidades, extremos
municipales, metodología). Regenerar con `pipeline/reporte.py`.

## Esquema `tasas.parquet` (tasa_natalidad_territorial)

`cvegeo, cve_ent, cve_mun, nombre_geografico, anio_ocurrencia,
nacimientos_totales, poblacion_mitad_anio, tasa_bruta_natalidad,
tasa_suavizada_trienal, tasa_fecundidad, flag_baja_escala, cohorte` — PK lógica
`(cvegeo, anio_ocurrencia, cohorte)`; incluye agregados estatales
(`cve_mun` null) y nacional (`cvegeo='00'`).
