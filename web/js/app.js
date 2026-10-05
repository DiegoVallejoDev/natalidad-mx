// app.js — bootstrap, filtros globales, exportaciones
import { S, loadAll, loadState, geojson, valuesOfYear, record, valueOf,
         pobOf, nombreOf, scopeName } from './data.js';
import { initMap, refreshValues, switchScope, captureHiResPNG,
         getMap } from './map.js';
import { updateAll, updateMeta, resizeAll, svgExports,
         updateSeries } from './charts.js';
import { fmtNum } from './classify.js';

function download(name, blob) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

export function onSelect() {
  updateAll();
  refreshBreadcrumb();
}

export async function drillTo(cve) {
  await loadState(cve);
  switchScope(cve);
  document.getElementById('btn-back').classList.remove('hidden');
  refreshBreadcrumb();
  updateAll();
}

export function backToNational() {
  switchScope('nacional');
  document.getElementById('btn-back').classList.add('hidden');
  refreshBreadcrumb();
  updateAll();
}

function refreshBreadcrumb() {
  const sel = S.selected
    ? ` · ${nombreOf(record(S.selected), S.selected)} ${S.selected}` : '';
  document.getElementById('breadcrumb').textContent =
    (S.scope !== 'nacional'
      ? `${scopeName()} · ${geojson().features.length} municipios`
      : 'México · 32 entidades federativas') + sel;
}

function refresh() {
  refreshValues();
  updateAll();
  refreshBreadcrumb();
}

// ---------- exportaciones ----------

function exportCSV() {
  const yr = valuesOfYear();
  const hdr = ['cvegeo', 'nombre', 'anio', 'cohorte',
               'nacimientos', 'poblacion', 'tbn', 'tbn_suavizada',
               'tfr', 'metrica_valor', 'flag_baja_escala'];
  const rows = [hdr.join(',')];
  for (const cg of Object.keys(yr).sort()) {
    const r = record(cg);
    const coh = r.c[S.cohort] || r.c.todas;
    rows.push([
      cg, `"${nombreOf(r, cg)}"`, S.year, S.cohort,
      coh[0], pobOf(r), r.c.todas[1], r.c.todas[2],
      r.tf ?? '', valueOf(r), r.f,
    ].join(','));
  }
  download(`natalidad_${S.scope}_${S.year}_${S.cohort}.csv`,
           new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' }));
}

async function exportParquet() {
  const buf = await fetch('data/tasas.parquet').then(r => r.arrayBuffer());
  download('tasa_natalidad_territorial.parquet',
           new Blob([buf], { type: 'application/octet-stream' }));
}

async function exportGeoJSON() {
  // capa del scope activo ya en memoria — clona y enriquece atributos
  const gj = JSON.parse(JSON.stringify(geojson()));
  for (const f of gj.features) {
    const cg = f.properties.cvegeo;
    const r = record(cg);
    const coh = r?.c[S.cohort] || r?.c.todas || [null, null, null];
    f.properties = {
      ...f.properties,
      anio: S.year,
      cohorte: S.cohort,
      nacimientos: coh[0],
      poblacion: r?.v[1] ?? null,
      tbn: r?.c.todas[1] ?? null,
      tbn_suavizada: r?.c.todas[2] ?? null,
      tfr: r?.tf ?? null,
      metrica_valor: r ? valueOf(r) : null,
      flag_baja_escala: r?.f === 1,
    };
  }
  download(`natalidad_${S.scope}_enriquecido_${S.year}.geojson`,
           new Blob([JSON.stringify(gj)], { type: 'application/geo+json' }));
}

async function exportPNG() {
  const btn = document.getElementById('exp-png');
  btn.disabled = true; btn.textContent = '…';
  try {
    const url = await captureHiResPNG();
    const blob = await (await fetch(url)).blob();
    download(`mapa_natalidad_${S.scope}_${S.year}.png`, blob);
  } finally {
    btn.disabled = false; btn.textContent = 'PNG';
  }
}

function exportSVG() {
  for (const { id, svg } of svgExports()) {
    download(`${id}_${S.year}.svg`,
             new Blob([svg], { type: 'image/svg+xml' }));
  }
}

// ---------- bootstrap ----------

async function main() {
  await loadAll();

  const ysel = document.getElementById('ctl-year');
  ysel.innerHTML = S.meta.anios
    .map(y => `<option ${y === S.year ? 'selected' : ''}>${y}</option>`)
    .join('');
  const csel = document.getElementById('ctl-cohort');
  csel.innerHTML = S.meta.cohortes
    .map(c => `<option value="${c.id}">${c.label}</option>`).join('');

  ysel.onchange = e => { S.year = +e.target.value; refresh(); };
  csel.onchange = e => { S.cohort = e.target.value; refresh(); };
  document.getElementById('ctl-metric').onchange = e => {
    S.metric = e.target.value; refresh(); };
  document.getElementById('ctl-class').onchange = e => {
    S.klass = e.target.value; refreshValues(); };
  document.getElementById('ctl-smooth').onchange = e => {
    S.smooth = e.target.checked; refresh(); };
  document.getElementById('btn-back').onclick = backToNational;

  document.getElementById('exp-csv').onclick = exportCSV;
  document.getElementById('exp-pq').onclick = exportParquet;
  document.getElementById('exp-geo').onclick = exportGeoJSON;
  document.getElementById('exp-png').onclick = exportPNG;
  document.getElementById('exp-svg').onclick = exportSVG;

  window.addEventListener('resize', resizeAll);

  updateMeta();
  initMap();
}

main().catch(err => {
  document.body.innerHTML =
    `<pre style="color:#f66;padding:20px">Error: ${err.stack}</pre>`;
});
