"""RNF-01/02 — Capas vectoriales TopoJSON.

Entrada: sources/5129746/mx_tj.json — TopoJSON INEGI MGN con objetos
'states' (32, state_code) y 'municipalities' (2436, state_code+mun_code).

Salidas (web/data/):
- mx_estados.topojson      props: cvegeo (2), nombre
- mun_<cve_ent>.topojson   municipios por estado, carga bajo drill-down
- mun_<cve_ent>.geojson    capa enriquecible para RF-06.2
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path("/home/ubuntu/repos/natalidad-mx")
OUT = ROOT / "web/data"
SRC_GIST = Path("/home/ubuntu/sources/5129746/mx_tj.json")
CAT = json.loads((ROOT / "data/catalogos/catalogos.json").read_text())
NOM_ENT = CAT["ageeml"]["entidades"]
MUN = {k: v["nombre"] for k, v in CAT["ageeml"]["municipios"].items()}


def run(cmd: list[str]) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, check=True)


def shp(target: str, out: Path, simplify: str | None = None,
        extra: list[str] | None = None) -> None:
    """Extrae un objeto del topojson y reexporta con propiedades limpias."""
    tmp = OUT / "_tmp.topojson"
    cmd = ["npx", "-y", "mapshaper", str(SRC_GIST),
           "-target", target]
    if extra:
        cmd += extra
    if simplify:
        cmd += ["-simplify", "visvalingam", simplify, "keep-shapes"]
    cmd += ["-o", str(tmp), "format=topojson", "quantization=1e6", "force"]
    run(cmd)
    (tmp, d) = (None, json.loads(tmp.read_text()))
    geoms = d["objects"][list(d["objects"].keys())[0]]["geometries"]
    for g in geoms:
        p = g["properties"]
        sc = str(p["state_code"]).zfill(2)
        if "mun_code" in p:
            cg = sc + str(p["mun_code"]).zfill(3)
            g["properties"] = {"cvegeo": cg, "nombre": MUN.get(cg,
                                                             p["mun_name"])}
        else:
            g["properties"] = {"cvegeo": sc,
                               "nombre": NOM_ENT.get(sc, p["state_name"])}
    OUT.joinpath("_tmp2.topojson").write_text(json.dumps(d))
    run(["npx", "-y", "mapshaper", str(OUT / "_tmp2.topojson"),
         "-o", str(out), "format=topojson", "quantization=1e6", "force"])
    (OUT / "_tmp.topojson").unlink()
    (OUT / "_tmp2.topojson").unlink()


def geojson_estado(cve: str) -> None:
    """RF-06.2: GeoJSON municipal por estado con atributos calculables."""
    run(["npx", "-y", "mapshaper", str(OUT / f"mun_{cve}.topojson"),
         "-o", str(OUT / f"mun_{cve}.geojson"), "format=geojson",
         "precision=0.0001", "force"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    shp("states", OUT / "mx_estados.topojson", simplify="30%")
    for cve in sorted(NOM_ENT):
        shp("municipalities", OUT / f"mun_{cve}.topojson",
            extra=["-filter", f"state_code=={int(cve)}"])
        geojson_estado(cve)
    for f in sorted(OUT.glob("mun_*.topojson")):
        print(f"{f.name}: {f.stat().st_size/1024:.0f} KB")
    print(f"mx_estados.topojson: "
          f"{(OUT/'mx_estados.topojson').stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    main()
