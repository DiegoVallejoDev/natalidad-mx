"""reporte.py — resumen analítico PDF de natalidad México.

Lee los payloads JSON ya generados por build.py (web/data/) y produce
docs/reporte_natalidad_mx.html, auto-contenido y listo para imprimir a PDF:
    google-chrome --headless=new --print-to-pdf=docs/reporte_natalidad_mx.pdf \
        --no-pdf-header-footer docs/reporte_natalidad_mx.html
"""
import json
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "web" / "data"
OUT_HTML = ROOT / "docs" / "reporte_natalidad_mx.html"

YEAR_REF = "2024"
YEAR_BASE = "2010"


def load(name):
    return json.load(open(DATA / name))


def bar(value, lo, hi, color="#4c9be8", width=90):
    """Barra CSS proporcional (ancho px)."""
    w = 0 if hi == lo else (value - lo) / (hi - lo)
    return (f'<span class="bar"><span class="fill" '
            f'style="width:{w * width:.0f}px;background:{color}"></span></span>')


def fmt(n, d=0):
    if n is None:
        return "—"
    return f"{n:,.{d}f}"


def main():
    ent = load("tasas_ent.json")["years"]
    cat = load("catalogo.json")

    # ---- serie nacional ('00') ----
    nat = {a: ent[a]["00"] for a in ent}
    years = sorted(nat)

    tbn0, tbn1 = nat[YEAR_BASE]["c"]["todas"][1], nat[YEAR_REF]["c"]["todas"][1]
    tf0, tf1 = nat[YEAR_BASE]["tf"], nat[YEAR_REF]["tf"]
    nac1 = nat[YEAR_REF]["c"]["todas"][0]
    adol1 = nat[YEAR_REF]["c"]["adol"][0]
    pct_adol = 100 * adol1 / nac1
    below = next((a for a in years if (nat[a]["tf"] or 9) < 2.1), None)
    decline = 100 * (tbn1 - tbn0) / tbn0
    tbns = [nat[a]["c"]["todas"][1] for a in years]
    tb_lo, tb_hi = min(tbns), max(tbns)

    rows_nat = "".join(
        f"<tr><td>{a}</td><td class='r'>{fmt(nat[a]['c']['todas'][0])}</td>"
        f"<td class='r'>{fmt(nat[a]['v'][1])}</td>"
        f"<td class='r'>{fmt(nat[a]['c']['todas'][1], 2)}</td>"
        f"<td class='r'>{fmt(nat[a]['tf'], 2)}"
        f"{bar(nat[a]['c']['todas'][1], tb_lo, tb_hi)}</td></tr>"
        for a in years)

    # ---- tabla estatal ----
    ent24 = {k: v for k, v in ent[YEAR_REF].items() if k != "00"}
    ent_sorted = sorted(ent24.items(),
                        key=lambda kv: kv[1]["c"]["todas"][1], reverse=True)
    e_tb = [v["c"]["todas"][1] for _, v in ent_sorted]
    rows_ent = "".join(
        f"<tr><td class='r'>{i + 1}</td><td>{v['n']}</td>"
        f"<td class='r'>{fmt(v['c']['todas'][1], 2)}"
        f"{bar(v['c']['todas'][1], min(e_tb), max(e_tb))}</td>"
        f"<td class='r'>{fmt(v['tf'], 2)}</td>"
        f"<td class='r'>{fmt(v['c']['todas'][0])}</td>"
        f"<td class='r'>{fmt(v['v'][1])}</td></tr>"
        for i, (_, v) in enumerate(ent_sorted))
    n_below = sum(1 for _, v in ent_sorted if (v["tf"] or 0) < 2.1)

    # ---- extremos municipales nacionales ----
    mun_all = []
    for cve in sorted(ent24):
        mun = load(f"tasas_mun_{cve}.json")["years"]
        for cg, r in mun[YEAR_REF].items():
            mun_all.append((r["n"], cg, r["c"]["todas"][1],
                            r["tf"], r["v"][1], r["f"]))
    estables = [m for m in mun_all if m[4] >= 10000]
    top = sorted(estables, key=lambda m: -m[2])[:10]
    bot = sorted(estables, key=lambda m: m[2])[:10]
    flag_ct = sum(1 for m in mun_all if m[5] == 1)

    def mun_rows(items):
        return "".join(
            f"<tr><td class='r'>{i + 1}</td><td>{n} <span class='cv'>{cg}"
            f"</span></td><td class='r'>{fmt(tb, 2)}</td>"
            f"<td class='r'>{fmt(tf, 2)}</td><td class='r'>{fmt(p)}</td></tr>"
            for i, (n, cg, tb, tf, p, _f) in enumerate(items))

    excl = cat["exclusiones"]
    today = dt.date.today().isoformat()

    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Natalidad MX · Resumen analítico {YEAR_REF}</title>
<style>
  @page {{ margin: 16mm 14mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font: 11px/1.45 "Helvetica Neue", Arial, sans-serif;
         color: #1b1f24; max-width: 780px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin: 0 0 2px; }}
  h2 {{ font-size: 14px; margin: 22px 0 6px; color: #0b5394;
       border-bottom: 1.5px solid #0b5394; padding-bottom: 2px;
       page-break-after: avoid; }}
  .sub {{ color: #555; margin: 0 0 14px; }}
  .kpi {{ display: flex; gap: 10px; margin: 10px 0 4px; }}
  .kpi div {{ flex: 1; border: 1px solid #d0d7de; border-radius: 6px;
              padding: 8px 10px; }}
  .kpi b {{ display: block; font-size: 17px; color: #0b5394; }}
  .kpi span {{ font-size: 9px; color: #555; }}
  table {{ width: 100%; border-collapse: collapse; margin: 6px 0;
           font-size: 10px; }}
  th {{ text-align: left; background: #eef3f8; padding: 3px 6px;
       border-bottom: 1px solid #b9c7d4; }}
  td {{ padding: 2px 6px; border-bottom: 1px solid #e6ebf0; }}
  td.r, th.r {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .bar {{ display: inline-block; vertical-align: middle; margin-left: 6px;
          height: 7px; background: #eef3f8; width: 90px; border-radius: 2px; }}
  .fill {{ display: block; height: 7px; border-radius: 2px; }}
  .cv {{ color: #888; font-size: 9px; }}
  .cols {{ display: flex; gap: 16px; }}
  .cols > div {{ flex: 1; }}
  ul {{ margin: 6px 0; padding-left: 18px; }}
  li {{ margin: 3px 0; }}
  .meta {{ font-size: 9.5px; color: #555; background: #f6f8fa;
           border: 1px solid #e0e5ea; border-radius: 6px;
           padding: 8px 12px; margin-top: 8px; }}
  .foot {{ margin-top: 18px; font-size: 9px; color: #888;
           border-top: 1px solid #ddd; padding-top: 6px; }}
  .pb {{ page-break-before: always; }}
</style></head><body>

<h1>Natalidad MX — Resumen analítico de natalidad</h1>
<p class="sub">Tasa bruta de natalidad (TBN) y tasa global de fecundidad (TFR)
por residencia habitual de la madre · ocurrencia · México {YEAR_BASE}–{YEAR_REF}
· generado {today}</p>

<div class="kpi">
  <div><b>{fmt(tbn1, 2)}‰</b><span>TBN nacional {YEAR_REF}
    ({fmt(tbn0, 2)} en {YEAR_BASE}, {decline:.0f}%)</span></div>
  <div><b>{fmt(tf1, 2)}</b><span>TFR nacional {YEAR_REF}
    ({fmt(tf0, 2)} en {YEAR_BASE}; umbral reemplazo 2.1)</span></div>
  <div><b>{fmt(nac1)}</b><span>Nacimientos {YEAR_REF} (SINAC)</span></div>
  <div><b>{pct_adol:.1f}%</b><span>de madres adolescentes (&lt;20 años)</span></div>
</div>

<h2>Hallazgos</h2>
<ul>
  <li>La TBN nacional cayó de <b>{fmt(tbn0, 2)}‰</b> ({YEAR_BASE}) a
      <b>{fmt(tbn1, 2)}‰</b> ({YEAR_REF}), una contracción de
      {abs(decline):.0f}% en 14 años.</li>
  <li>La TFR nacional pasó de {fmt(tf0, 2)} a <b>{fmt(tf1, 2)}</b> hijos por
      mujer; el país cruzó por debajo del nivel de reemplazo (2.1)
      {"en " + str(below) if below else "— aún no"}.</li>
  <li>En {YEAR_REF}, <b>{n_below} de 32 entidades</b> ya registran TFR
      &lt; 2.1. Los máximos estatales se concentran en el sur-sureste.</li>
  <li>{flag_ct:,} municipios (de {len(mun_all):,}) tienen población &lt; 10,000
      hab. y se marcan con <i>flag de alta varianza</i>; para ellos conviene
      la media trienal.</li>
</ul>

<h2>Serie nacional</h2>
<table><tr><th>Año</th><th class="r">Nacimientos</th>
  <th class="r">Población mitad de año</th><th class="r">TBN ‰</th>
  <th class="r">TFR</th></tr>{rows_nat}</table>

<h2 class="pb">Entidades federativas · {YEAR_REF} (orden por TBN)</h2>
<table><tr><th class="r">#</th><th>Entidad</th><th class="r">TBN ‰</th>
  <th class="r">TFR</th><th class="r">Nacimientos</th>
  <th class="r">Población</th></tr>{rows_ent}</table>

<div class="cols pb">
  <div><h2>Top 10 municipal · TBN {YEAR_REF}</h2>
    <table><tr><th class="r">#</th><th>Municipio</th><th class="r">TBN ‰</th>
      <th class="r">TFR*</th><th class="r">Pob.</th></tr>
      {mun_rows(top)}</table></div>
  <div><h2>Bottom 10 municipal · TBN {YEAR_REF}</h2>
    <table><tr><th class="r">#</th><th>Municipio</th><th class="r">TBN ‰</th>
      <th class="r">TFR*</th><th class="r">Pob.</th></tr>
      {mun_rows(bot)}</table></div>
</div>
<p class="cv">* Solo municipios con población ≥ 10,000 (sin flag de alta
varianza). TFR municipal = aproximación con estructura de edad estatal.</p>

<h2>Metodología</h2>
<ul>
  <li><b>Ocurrencia, no registro</b>: cada evento se asigna a su año de
      ocurrencia (mitiga subregistro extemporáneo).</li>
  <li><b>Residencia habitual de la madre</b> (CVE_ENT/CVE_MUN residencia);
      nacimientos de madres con residencia extranjera
      ({fmt(excl["EXTRANJERO"])}) o no especificada
      ({fmt(excl["NO_ESPECIFICADO"])}) se excluyen del mapa.</li>
  <li><b>TBN</b> = nacimientos / población CONAPO mitad de año × 1,000.
      <b>TBN suavizada</b> = media móvil trienal centrada.</li>
  <li><b>TFR</b> = 5·Σ B<sub>g</sub>/W<sub>g</sub> sobre grupos quinquenales
      femeninos 15–49 (CONAPO). Umbral de reemplazo: 2.1 hijos/mujer.
      A nivel municipal los denominadores por edad se aproximan escalando la
      estructura estatal por población femenina municipal.</li>
  <li><b>Flag de alta varianza</b>: unidades con población &lt; 10,000
      (tasas inestables por baja escala muestral).</li>
</ul>

<div class="meta"><b>Fuentes y cobertura.</b>
Nacimientos: {cat["fuentes"]["nacimientos"]} —
cubre ≈86–90% del registro civil (partos atendidos en unidades de salud),
por lo que los niveles son ligeramente conservadores; las tendencias y
razones relativas son robustas.
Población: {cat["fuentes"]["poblacion"]}.
Geometrías: {cat["fuentes"]["geometrias"]} (2,436 municipios,
Mayo 2021 — subdivisiones posteriores no incluidas).</div>

<p class="foot">Generado por <code>pipeline/reporte.py</code> a partir de los
payloads publicados en <code>web/data/</code> —
github.com/DiegoVallejoDev/natalidad-mx</p>
</body></html>"""

    OUT_HTML.parent.mkdir(exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"OK {OUT_HTML} ({OUT_HTML.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
