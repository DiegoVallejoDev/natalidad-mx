"""Catálogos geográficos: AGEEML (INEGI) y CATMPO/CatEstados (SaS).

Construye:
- catalogo CVEGEO -> nombre oficial (32 entidades + municipios)
- crosswalk  cve_sas (ent+mun) -> cvegeo INEGI, por emparejamiento de nombres
  dentro de cada entidad
- lookup (ent_inegi, nombre_norm) -> cve_mun para el layout viejo basado en
  nombres literales
"""
from __future__ import annotations

import csv
import json
import unicodedata
from pathlib import Path

import requests

from fields import norm_txt, JALISCO

RAW = Path("/home/ubuntu/data/raw")
SINCAT = RAW / "sincat"
OUT = Path("/home/ubuntu/repos/natalidad-mx/data/catalogos")
AGEEML_API = "https://gaia.inegi.org.mx/wscatgeo/v2"


def fetch_ageeml() -> dict:
    """Descarga el Catálogo Único de Claves AGEEML: entidades + municipios."""
    ent = requests.get(f"{AGEEML_API}/mgee", timeout=30).json()["datos"]
    entidades = {
        str(e["cve_ent"]).zfill(2): e["nomgeo"] for e in ent
        if str(e["cve_ent"]).zfill(2).isdigit() and int(e["cve_ent"]) <= 32
    }
    municipios = {}
    for cve in sorted(entidades):
        datos = requests.get(f"{AGEEML_API}/mgem/{cve}", timeout=30).json()["datos"]
        for m in datos:
            cg = str(m["cvegeo"]).zfill(5)
            municipios[cg] = {"nombre": m["nomgeo"], "cve_ent": cve,
                              "cve_mun": str(m["cve_mun"]).zfill(3)}
    return {"entidades": entidades, "municipios": municipios}


def load_sas_catalogos(catdir: Path = SINCAT) -> dict:
    """Lee CatEstados.csv (SaS entidades) y CATMPO.csv (SaS municipios)."""
    estados = {}
    with open(catdir / "CatEstados.csv", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            estados[row["EDO"].strip().strip('"')] = row["DESCRIP"].strip().strip('"')
    municipios = {}  # (edo_sas, mpo_sas) -> descrip
    with open(catdir / "CATMPO.csv", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            municipios[(row["EDO"].strip().strip('"'),
                        row["MPO"].strip().strip('"'))] = row["DESCRIP"].strip().strip('"')
    return {"estados": estados, "municipios": municipios}


def build_crosswalk(ageeml: dict, sas: dict) -> dict:
    """Mapea (edo_sas, mpo_sas) -> cvegeo INEGI por nombre dentro de la entidad.

    Los códigos de entidad SaS 01-32 coinciden con INEGI. Los municipios se
    emparejan por nombre normalizado; si el código coincide con INEGI y no hay
    conflicto de nombre, se acepta la identidad como respaldo.
    """
    inegi_by_ent = {}
    for cg, m in ageeml["municipios"].items():
        inegi_by_ent.setdefault(m["cve_ent"], {})[norm_txt(m["nombre"])] = cg

    cross, ambiguos = {}, []
    for (edo, mpo), nombre in sas["municipios"].items():
        ent = edo.zfill(2)
        if ent not in inegi_by_ent:
            continue
        n = norm_txt(nombre)
        tabla = inegi_by_ent[ent]
        if n in tabla:
            cross[f"{ent}{mpo}"] = tabla[n]
            continue
        # fallback: identidad de código si el nombre INEGI es único por clave
        cg = f"{ent}{mpo}"
        if cg in ageeml["municipios"]:
            cross[f"{ent}{mpo}"] = cg
        else:
            ambiguos.append((edo, mpo, nombre))
    return {"sas2inegi": cross, "sin_match": ambiguos}


def build_name_lookup(ageeml: dict) -> dict:
    """(cve_ent, nombre_norm) -> cve_mun para el layout viejo (nombres)."""
    lookup = {}
    for cg, m in ageeml["municipios"].items():
        key = f"{m['cve_ent']}|{norm_txt(m['nombre'])}"
        lookup[key] = m["cve_mun"]
    return lookup


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sas_zip = RAW / "sinac" / "sinac_catalogos_2015-2019.zip"
    if not SINCAT.exists():
        import zipfile
        SINCAT.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(sas_zip) as z:
            z.extractall(SINCAT)
    ageeml = fetch_ageeml()
    sas = load_sas_catalogos()
    cross = build_crosswalk(ageeml, sas)
    names = build_name_lookup(ageeml)
    result = {
        "ageeml": ageeml,
        "sas_estados": sas["estados"],
        "sas_municipios": {f"{e}|{m}": n for (e, m), n in sas["municipios"].items()},
        "sas2inegi": cross["sas2inegi"],
        "sas_sin_match": cross["sin_match"],
        "nombre2cvemun": names,
    }
    (OUT / "catalogos.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1))
    n_jal = sum(1 for k in cross["sas2inegi"] if k.startswith(JALISCO))
    print(f"entidades INEGI: {len(ageeml['entidades'])}")
    print(f"municipios INEGI: {len(ageeml['municipios'])}")
    print(f"crosswalk SaS->INEGI: {len(cross['sas2inegi'])} (Jalisco: {n_jal})")
    print(f"SaS sin match: {len(cross['sin_match'])}")
    for row in cross["sin_match"][:15]:
        print("   ?", row)


if __name__ == "__main__":
    main()
