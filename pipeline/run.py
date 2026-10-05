"""Orquestador del pipeline ETL completo.

Uso:
    python -m pipeline.run                # todo el flujo
    python -m pipeline.run --solo build   # una sola etapa

Etapas: catalogos → ingest (SINAC→interim) → poblacion (CONAPO→interim)
        → build (tasas+JSON cliente) → geometrias (TopoJSON/GeoJSON)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ETAPAS = ["catalogos", "ingest", "poblacion", "build", "geometrias"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", choices=ETAPAS,
                    help="Ejecuta solo una etapa del pipeline")
    args = ap.parse_args()

    etapas = [args.solo] if args.solo else ETAPAS
    for etapa in etapas:
        t0 = time.time()
        print(f"\n=== {etapa} ===", flush=True)
        mod = __import__(f"pipeline.{etapa}", fromlist=["main"])
        mod.main()
        print(f"--- {etapa}: {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
