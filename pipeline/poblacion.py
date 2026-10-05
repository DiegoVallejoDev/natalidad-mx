"""Denominador CONAPO: proyección de población a mitad de año.

Fuente: diegovalle/conapo-2010 (datos CONAPO 2010 ya limpios)
- clean-data/municipio-population2010-2030.csv : Population, Code, Sex, Year
- clean-data/state-population.csv              : Females, Males, Total, Year,
                                                 StateCode, StateName

Salida: data/interim/poblacion.parquet  (cvegeo|cve_ent, anio, pob)
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

SRC = Path("/home/ubuntu/sources/conapo-2010/clean-data")
INTERIM = Path("/home/ubuntu/repos/natalidad-mx/data/interim")


def main() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)

    mun = pl.read_csv(SRC / "municipio-population2010-2030.csv")
    mun = (mun.filter(pl.col("Sex") == "Total")
              .with_columns(
                  pl.col("Code").cast(pl.Utf8).str.strip_chars()
                    .str.pad_start(5, "0").alias("cvegeo"))
              .rename({"Year": "anio", "Population": "pob"})
              .select(["cvegeo", "anio", "pob"]))

    ent = pl.read_csv(SRC / "state-population.csv")
    ent = (ent.with_columns(
                pl.col("StateCode").cast(pl.Utf8).str.strip_chars()
                  .str.pad_start(2, "0").alias("cve_ent"))
             .rename({"Year": "anio", "Total": "pob"})
             .select(["cve_ent", "anio", "pob"]))

    mun.write_parquet(INTERIM / "poblacion_mun.parquet")
    ent.write_parquet(INTERIM / "poblacion_ent.parquet")
    jal = mun.filter(pl.col("cvegeo").str.starts_with("14") &
                   (pl.col("anio") == 2020))
    print(f"municipios: {len(mun):,} filas; Jalisco 2020: {len(jal)} munis, "
          f"pob total {jal['pob'].sum():,}")
    print(f"entidades: {len(ent):,} filas; rango {ent['anio'].min()}-"
          f"{ent['anio'].max()}")


if __name__ == "__main__":
    main()
