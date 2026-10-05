"""RF-01 — Ingesta SINAC: ocurrencia, residencia habitual, cohortes.

Por cada año ZIP en data/raw/sinac:
1. Extrae el CSV (una vez) a data/raw/sinac/csv/
2. Detecta el layout y mapea columnas canónicas vía ALIASES
3. Normaliza: año de OCURRENCIA (no de registro), residencia habitual
   (ent+mun) -> CVEGEO INEGI, cohorte de edad materna
4. Buckets no mapeables: EXTRANJERO / NO_ESPECIFICADO (RF-01.2)
5. Agrega (cvegeo, anio_ocurrencia, cohorte) -> conteos -> parquet
"""
from __future__ import annotations

import json
import sys
import time
import zipfile
from pathlib import Path

import polars as pl

from fields import (ALIASES, COHORTES, ENT_SAS_EXTRANJERO,
                    ENT_SAS_NOESP, MUN_NOESP, NOMBRE_ENT_EXTRANJERO,
                    NOMBRE_ENT_NOESP, norm_txt)

RAW = Path("/home/ubuntu/data/raw/sinac")
CSV_DIR = RAW / "csv"
INTERIM = Path("/home/ubuntu/repos/natalidad-mx/data/interim")
CATALOGOS = Path("/home/ubuntu/repos/natalidad-mx/data/catalogos/catalogos.json")

cat = json.loads(CATALOGOS.read_text())
SAS2INEGI = cat["sas2inegi"]                    # "EEmmm" SaS -> cvegeo INEGI
SAS_MUN_NOMBRE = {}                            # "14|ACATIC" -> "001"
for k, v in cat["sas_municipios"].items():
    e, m = k.split("|")
    SAS_MUN_NOMBRE[f"{e}|{norm_txt(v)}"] = m
SAS_ENT_NOMBRE = {norm_txt(v): k for k, v in cat["sas_estados"].items()}
SAS_ENT_NOMBRE.update({
    "CIUDAD DE MEXICO": "09", "CDMX": "09", "MEXICO DF": "09",
    "EDOMEX": "15", "ESTADO DE MEXICO": "15", "MEXICO": "15",
    "COAHUILA": "05", "MICHOACAN": "16", "QUERETARO": "22",
    "VERACRUZ": "30", "SAN LUIS POTOSI": "24", "NUEVO LEON": "19",
    "BAJA CALIFORNIA SUR": "03",
})
for n in NOMBRE_ENT_EXTRANJERO:
    SAS_ENT_NOMBRE[n] = "99X"   # sentinel extranjero
for n in NOMBRE_ENT_NOESP:
    SAS_ENT_NOMBRE[n] = "99N"   # sentinel no especificado


def _norm(c: str) -> pl.Expr:
    return (
        pl.col(c).cast(pl.Utf8).str.strip_chars().str.to_uppercase()
        .str.replace_all("[ÁÀÄÂ]", "A").str.replace_all("[ÉÈËÊ]", "E")
        .str.replace_all("[ÍÌÏÎ]", "I").str.replace_all("[ÓÒÖÔ]", "O")
        .str.replace_all("[ÚÙÜÛ]", "U").str.replace_all("Ñ", "N")
        .str.replace_all(r"[^A-Z0-9 ]", " ")
        .str.replace_all(r"\s+", " ").str.strip_chars()
    )


def find_csv(year: int) -> Path:
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    out = CSV_DIR / f"nac_{year}.csv"
    if out.exists():
        return out
    z = RAW / f"sinac_{year}.zip"
    with zipfile.ZipFile(z) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        print(f"   extrayendo {name} ({zf.getinfo(name).file_size/1e6:.0f} MB)")
        with zf.open(name) as src, open(out, "wb") as dst:
            while chunk := src.read(1 << 22):
                dst.write(chunk)
    return out


def resolve_columns(csv_path: Path) -> tuple[dict[str, str], bool]:
    """Devuelve (canonico -> nombre_real_en_csv, layout_por_nombres)."""
    with open(csv_path, "rb") as f:
        header = f.readline().decode("utf-8", "replace").strip()
    raw_cols = [c.strip().strip('"') for c in header.split(",")]
    lower = {c.lower(): c for c in raw_cols}
    resolved = {}
    for canon, aliases in ALIASES.items():
        for a in aliases:
            if a in lower:
                resolved[canon] = lower[a]
                break
    faltantes = set(ALIASES) - set(resolved)
    if faltantes:
        raise ValueError(f"columnas no resueltas: {faltantes}; header={raw_cols[:15]}")
    name_layout = (resolved["ent_residencia"].lower() == "entidad_residencia_madre"
                   and resolved["mun_residencia"].lower()
                   == "municipio_residencia_madre")
    return resolved, name_layout


def cohorte_expr() -> pl.Expr:
    e = pl.col("edad_madre").cast(pl.Int32, strict=False)
    expr = pl.when(e.is_between(0, 19)).then(pl.lit("adol"))
    for cid, _label, lo, hi in COHORTES[1:-1]:
        expr = expr.when(e.is_between(lo, hi)).then(pl.lit(cid))
    expr = expr.when(e.is_between(40, 120)).then(pl.lit("e40mas"))
    return expr.otherwise(pl.lit("ne")).alias("cohorte")


def process_year(year: int) -> tuple[pl.DataFrame, pl.DataFrame]:
    csv_path = find_csv(year)
    res, name_layout = resolve_columns(csv_path)
    t0 = time.time()

    lf = (
        pl.scan_csv(csv_path, infer_schema_length=0,
                    null_values=["", "NA", "N/A"],
                    truncate_ragged_lines=True,
                    encoding="utf8-lossy")
        .select([res[k] for k in res])
        .rename({v: k for k, v in res.items()})
    )

    fecha = pl.col("fecha_nacimiento").str.strip_chars()
    lf = lf.with_columns([
        pl.when(fecha.str.len_chars() >= 8)
          .then(fecha.str.slice(-4))
          .otherwise(fecha.str.slice(0, 4))
          .cast(pl.Int32, strict=False).alias("anio"),
        cohorte_expr(),
    ])
    lf = lf.filter(pl.col("anio").is_between(1990, 2030))

    if name_layout:
        lf = lf.with_columns([
            _norm("ent_residencia").alias("_ent_n"),
            _norm("mun_residencia").alias("_mun_n"),
        ])
        lf = lf.with_columns(
            pl.col("_ent_n").replace(SAS_ENT_NOMBRE).alias("_edo_sas"))
        lf = lf.with_columns(
            pl.when(pl.col("_edo_sas").is_not_null())
              .then(pl.concat_str([pl.col("_edo_sas"), pl.lit("|"),
                                   pl.col("_mun_n")]))
              .otherwise(None).alias("_key_mun"))
        lf = lf.with_columns(
            pl.col("_key_mun").replace(SAS_MUN_NOMBRE).alias("_mpo_sas"))
        lf = lf.with_columns(
            pl.when(pl.col("_edo_sas") == "99X").then(pl.lit("EXTRANJERO"))
              .when((pl.col("_edo_sas") == "99N") | pl.col("_edo_sas").is_null()
                    | pl.col("_mpo_sas").is_null())
              .then(pl.lit("NO_ESPECIFICADO"))
              .otherwise(pl.concat_str([pl.col("_edo_sas"),
                                        pl.col("_mpo_sas")]))
              .alias("_sas_key"))
    else:
        ent = pl.col("ent_residencia").str.strip_chars()
        mun = pl.col("mun_residencia").str.strip_chars()
        ent2 = (pl.when(ent.str.len_chars() == 1)
                .then(pl.lit("0") + ent).otherwise(ent))
        mun3 = (pl.when(mun.str.len_chars() == 1).then(pl.lit("00") + mun)
                .when(mun.str.len_chars() == 2).then(pl.lit("0") + mun)
                .otherwise(mun))
        lf = lf.with_columns(
            pl.when(ent2.is_in(ENT_SAS_EXTRANJERO)).then(pl.lit("EXTRANJERO"))
              .when(ent2.is_in(ENT_SAS_NOESP) | mun3.is_in(MUN_NOESP)
                    | ent2.is_null() | mun3.is_null())
              .then(pl.lit("NO_ESPECIFICADO"))
              .otherwise(pl.concat_str([ent2, mun3])).alias("_sas_key"))

    lf = lf.with_columns(
        pl.col("_sas_key").replace(SAS2INEGI).alias("cvegeo"))
    lf = lf.with_columns(
        pl.when(pl.col("_sas_key") == "EXTRANJERO").then(pl.lit("EXTRANJERO"))
          .when(pl.col("_sas_key") == "NO_ESPECIFICADO")
          .then(pl.lit("NO_ESPECIFICADO"))
          .when(pl.col("cvegeo").is_null()).then(pl.lit("NO_MAPEADO"))
          .otherwise(pl.lit("OK")).alias("_status"))

    agg = (lf.group_by(["cvegeo", "anio", "cohorte", "_status"])
             .len().collect(engine="streaming"))
    nac = (agg.filter(pl.col("_status") == "OK")
              .rename({"len": "nacimientos"})
              .select(["cvegeo", "anio", "cohorte", "nacimientos"]))
    exc = (agg.filter(pl.col("_status") != "OK")
              .group_by(["_status", "anio", "cohorte"])
              .agg(pl.col("len").sum().alias("nacimientos")))
    dt = time.time() - t0
    total = int(agg["len"].sum())
    ok = int(nac["nacimientos"].sum())
    print(f"   {year}: {total:,} filas -> OK {ok:,} ({ok/total:.1%}) "
          f"[{dt:.0f}s] layout={'nombres' if name_layout else 'claves'}")
    return nac, exc


def main() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    years = [int(a) for a in sys.argv[1:]] or list(range(2010, 2025))
    nacs, excs = [], []
    for y in years:
        n, e = process_year(y)
        nacs.append(n); excs.append(e)
    nac_all = pl.concat(nacs).group_by(["cvegeo", "anio", "cohorte"]).agg(
        pl.col("nacimientos").sum())
    exc_all = pl.concat(excs).group_by(["_status", "anio", "cohorte"]).agg(
        pl.col("nacimientos").sum())
    nac_all.write_parquet(INTERIM / "nacimientos.parquet")
    exc_all.write_parquet(INTERIM / "exclusiones.parquet")
    print(f"\nnacimientos.parquet: {len(nac_all):,} filas")
    print(exc_all.group_by("_status").agg(pl.col("nacimientos").sum()))


if __name__ == "__main__":
    main()
