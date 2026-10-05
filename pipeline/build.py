"""RF-01.3 / RF-03 — Motor de tasas + serialización para el cliente.

Lee:  interim/nacimientos.parquet  (cvegeo, anio, cohorte, nacimientos)
      interim/poblacion_mun.parquet (cvegeo, anio, pob)
      interim/poblacion_ent.parquet (cve_ent, anio, pob)
      catalogos/catalogos.json      (nombres AGEEML)

Genera en web/data/:
  tasas.parquet        — esquema tasa_natalidad_territorial del spec (todos los
                         municipios MX + agregados estatales + nacional)
  tasas_mun.json       — {names, years:{A:{cvegeo:[nac,pob,tbn,tbs,flag]}}}
  tasas_ent.json       — idem a nivel entidad (+ nacional cvegeo="00")
  catalogo.json        — metadatos: años, cohortes, fuentes, exclusiones
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl

ROOT = Path("/home/ubuntu/repos/natalidad-mx")
INTERIM = ROOT / "data/interim"
OUT = ROOT / "web/data"
CATALOGOS = ROOT / "data/catalogos/catalogos.json"
COHORTE_IDS = ["adol", "e20_24", "e25_29", "e30_34", "e35_39", "e40mas", "ne"]
UMBRAL = 10_000


def tbn(b: pl.Expr, p: pl.Expr) -> pl.Expr:
    return pl.when(p > 0).then(b * 1000.0 / p).otherwise(None)


def build_frame(nac: pl.DataFrame, pob: pl.DataFrame,
                key: str, nombres: dict) -> pl.DataFrame:
    """Pivot cohortes + join población + tasas (incluye 'todas')."""
    wide = (nac.group_by([key, "anio"])
               .agg([pl.col("nacimientos")
                     .filter(pl.col("cohorte") == c).sum().alias(f"b_{c}")
                     for c in COHORTE_IDS] +
                    [pl.col("nacimientos").sum().alias("b_todas")]))
    df = pob.join(wide, on=[key, "anio"], how="left")
    df = df.with_columns(
        [pl.col(f"b_{c}").fill_null(0) for c in COHORTE_IDS] +
        [pl.col("b_todas").fill_null(0)])

    cols = [key, "anio", "pob"]
    for c in ["todas"] + COHORTE_IDS:
        cols += [
            pl.col(f"b_{c}").alias(f"nac_{c}"),
            tbn(pl.col(f"b_{c}"), pl.col("pob")).alias(f"tbn_{c}"),
        ]
    df = df.select(cols)

    # suavizada trienal centrada por unidad (RF-03.2)
    df = df.sort([key, "anio"])
    for c in ["todas"] + COHORTE_IDS:
        df = df.with_columns(
            pl.col(f"tbn_{c}")
              .rolling_mean(3, center=True, min_samples=1)
              .over(key).alias(f"tbs_{c}"))
    df = df.with_columns(
        (pl.col("pob") < UMBRAL).alias("flag_baja_escala"))
    df = df.with_columns(
        pl.col(key).replace(nombres).alias("nombre_geografico"))
    return df


def to_records(df: pl.DataFrame, key: str) -> dict:
    """{anio: {cvegeo: {n, v:[nac,pob,tbn,tbs], f, c:{coh:[nac,tbn,tbs]}}}}"""
    years = {}
    cohortes = ["todas"] + COHORTE_IDS
    for row in df.iter_rows(named=True):
        y = str(row["anio"])
        coh = {}
        for c in cohortes:
            n = row[f"nac_{c}"]
            t = row[f"tbn_{c}"]
            s = row[f"tbs_{c}"]
            coh[c] = [n,
                      round(t, 2) if t is not None else None,
                      round(s, 2) if s is not None else None]
        years.setdefault(y, {})[row[key]] = {
            "n": row["nombre_geografico"] or row[key],
            "v": [coh["todas"][0], row["pob"], coh["todas"][1],
                  coh["todas"][2]],
            "f": int(row["flag_baja_escala"]), "c": coh,
        }
    return years


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cat = json.loads(CATALOGOS.read_text())
    nom_mun = {k: v["nombre"] for k, v in cat["ageeml"]["municipios"].items()}
    nom_ent = cat["ageeml"]["entidades"]

    nac = pl.read_parquet(INTERIM / "nacimientos.parquet")
    pob_m = pl.read_parquet(INTERIM / "poblacion_mun.parquet")
    pob_e = pl.read_parquet(INTERIM / "poblacion_ent.parquet")

    anios = sorted(nac["anio"].unique().to_list())
    print("años nacimientos:", anios)

    # --- municipios ---
    mun = build_frame(nac, pob_m.filter(pl.col("anio").is_in(anios)),
                      "cvegeo", nom_mun)

    # --- entidades: nacimientos agregados por cve_ent ---
    nac_e = (nac.with_columns(pl.col("cvegeo").str.slice(0, 2).alias("cve_ent"))
               .drop("cvegeo"))
    ent = build_frame(nac_e.rename({"cve_ent": "cvegeo"}),
                      pob_e.rename({"cve_ent": "cvegeo"})
                           .filter(pl.col("anio").is_in(anios)),
                      "cvegeo", nom_ent)

    # --- nacional (cvegeo="00") ---
    nac_n = nac.with_columns(pl.lit("00").alias("cvegeo"))
    pob_n = (pob_e.group_by("anio").agg(pl.col("pob").sum())
             .with_columns(pl.lit("00").alias("cvegeo"))
             .filter(pl.col("anio").is_in(anios)))
    nac_m = build_frame(nac_n, pob_n, "cvegeo",
                        {"00": "México (total)"})
    ent = pl.concat([ent, nac_m])

    # --- parquet consolidado (esquema del spec) ---
    spec = ent.select([
        pl.col("cvegeo"),
        pl.col("cvegeo").str.slice(0, 2).alias("cve_ent"),
        pl.when(pl.col("cvegeo").str.len_chars() == 5)
          .then(pl.col("cvegeo").str.slice(2, 3))
          .otherwise(None).alias("cve_mun"),
        "nombre_geografico",
        pl.col("anio").alias("anio_ocurrencia"),
        pl.col("nac_todas").alias("nacimientos_totales"),
        pl.col("pob").alias("poblacion_mitad_anio"),
        pl.col("tbn_todas").round(2).alias("tasa_bruta_natalidad"),
        pl.col("tbs_todas").round(2).alias("tasa_suavizada_trienal"),
        "flag_baja_escala",
    ])
    mun_spec = mun.select([
        pl.col("cvegeo"),
        pl.col("cvegeo").str.slice(0, 2).alias("cve_ent"),
        pl.col("cvegeo").str.slice(2, 3).alias("cve_mun"),
        "nombre_geografico",
        pl.col("anio").alias("anio_ocurrencia"),
        pl.col("nac_todas").alias("nacimientos_totales"),
        pl.col("pob").alias("poblacion_mitad_anio"),
        pl.col("tbn_todas").round(2).alias("tasa_bruta_natalidad"),
        pl.col("tbs_todas").round(2).alias("tasa_suavizada_trienal"),
        "flag_baja_escala",
    ])
    tabla = pl.concat([mun_spec, spec])
    tabla.write_parquet(OUT / "tasas.parquet")
    tabla.write_csv(OUT / "tasas.csv")

    jalisco_only = mun.filter(pl.col("cvegeo").str.starts_with("14"))
    (OUT / "tasas_mun.json").write_text(json.dumps(
        {"years": to_records(jalisco_only, "cvegeo")}, ensure_ascii=False,
        separators=(",", ":")))
    (OUT / "tasas_ent.json").write_text(json.dumps(
        {"years": to_records(ent, "cvegeo")}, ensure_ascii=False,
        separators=(",", ":")))

    exc = pl.read_parquet(INTERIM / "exclusiones.parquet")
    meta = {
        "anios": anios,
        "cohortes": [{"id": c, "label": l} for c, l, *_ in
                     [("todas", "Todas las edades")] +
                     [("adol", "Adolescentes (<20)"),
                      ("e20_24", "20–24"), ("e25_29", "25–29"),
                      ("e30_34", "30–34"), ("e35_39", "35–39"),
                      ("e40mas", "40+"), ("ne", "No especificada")]],
        "fuentes": {
            "nacimientos": "SINAC/SSa datos abiertos (ocurrencia)",
            "poblacion": "CONAPO proyecciones 2010–2030 (mitad de año)",
            "geometrias": "INEGI Marco Geoestadístico (TopoJSON)",
        },
        "exclusiones": {r["_status"]: r["nacimientos"] for r in
                        exc.group_by("_status")
                           .agg(pl.col("nacimientos").sum())
                           .iter_rows(named=True)},
    }
    (OUT / "catalogo.json").write_text(json.dumps(
        meta, ensure_ascii=False, indent=1))

    jal = mun.filter(pl.col("cvegeo").str.starts_with("14") &
                     (pl.col("anio") == 2022))
    print(f"Jalisco 2022: nac={jal['nac_todas'].sum():,}, "
          f"pob={jal['pob'].sum():,}, tbn={jal['nac_todas'].sum()/jal['pob'].sum()*1000:.1f}‰")
    print(f"archivos escritos en {OUT}")


if __name__ == "__main__":
    main()
