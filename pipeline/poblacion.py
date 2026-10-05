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

    # --- población femenina (denominadores de fecundidad) ---
    mun_f = pl.read_csv(SRC / "municipio-population2010-2030.csv")
    mun_f = (mun_f.filter(pl.col("Sex") == "Females")
                 .with_columns(
                     pl.col("Code").cast(pl.Utf8).str.strip_chars()
                       .str.pad_start(5, "0").alias("cvegeo"))
                 .rename({"Year": "anio", "Population": "pob_fem"})
                 .select(["cvegeo", "anio", "pob_fem"]))
    mun_f.write_parquet(INTERIM / "pob_fem_mun.parquet")

    ent_f = pl.read_csv(SRC / "state-population.csv")
    ent_f = (ent_f.with_columns(
                pl.col("StateCode").cast(pl.Utf8).str.strip_chars()
                  .str.pad_start(2, "0").alias("cve_ent"))
               .rename({"Year": "anio", "Females": "pob_fem"})
               .select(["cve_ent", "anio", "pob_fem"]))
    ent_f.write_parquet(INTERIM / "pob_fem_ent.parquet")

    # --- mujeres por grupo quinquenal 15-49 (TFR denominador estatal) ---
    GRUPOS = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]
    ag = pl.read_csv(SRC / "state-population-age-groups.csv")
    wf = (ag.filter(pl.col("AgeGroup").is_in(GRUPOS))
            .with_columns(
                pl.col("StateCode").cast(pl.Utf8).str.strip_chars()
                  .str.pad_start(2, "0").alias("cve_ent"),
                pl.col("AgeGroup").str.replace_all("-", "_")
                  .str.replace("40_44", "40_49")
                  .str.replace("45_49", "40_49")
                  .alias("g"))
            .rename({"Year": "anio"})
            .group_by(["cve_ent", "anio", "g"])
            .agg(pl.col("Females").sum())
            .pivot("g", index=["cve_ent", "anio"], values="Females")
            .rename({f"{g.replace('-', '_')}": f"wf_{g.replace('-', '_')}"
                     for g in ["15_19", "20_24", "25_29", "30_34", "35_39"]}))
    wf = wf.with_columns(
        sum(pl.col(c) for c in
            ["wf_15_19", "wf_20_24", "wf_25_29", "wf_30_34", "wf_35_39",
             "40_49"]).alias("wf_15_49"))
    wf = wf.rename({"40_49": "wf_40_49"})
    wf.write_parquet(INTERIM / "mujeres_fert_ent.parquet")

    jal = mun.filter(pl.col("cvegeo").str.starts_with("14") &
                   (pl.col("anio") == 2020))
    print(f"municipios: {len(mun):,} filas; Jalisco 2020: {len(jal)} munis, "
          f"pob total {jal['pob'].sum():,}")
    print(f"entidades: {len(ent):,} filas; rango {ent['anio'].min()}-"
          f"{ent['anio'].max()}")
    wfj = wf.filter(pl.col("cve_ent") == "14").sort("anio").tail(1)
    print("Jalisco mujeres 15-49 (últ. año):", wfj["wf_15_49"].to_list())


if __name__ == "__main__":
    main()
