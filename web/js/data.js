// data.js — carga e indexación O(1) de tasas y geometrías
export const S = {
  meta: null,
  ent: null,          // {years:{A:{cvegeo:{n,v,f,c}}}}
  states: {},         // cve_ent → {years, geo} bajo demanda (drill-down)
  geoEnt: null,       // FeatureCollection estados
  scope: 'nacional',  // 'nacional' | cve_ent ('14'…)
  year: null,
  cohort: 'todas',
  metric: 'tbn',      // 'tbn' | 'tfr' | 'nac'
  smooth: false,
  klass: 'jenks',
  selected: null,     // cvegeo seleccionado
};

export async function loadAll() {
  const [meta, ent, gEnt] = await Promise.all([
    fetch('data/catalogo.json').then(r => r.json()),
    fetch('data/tasas_ent.json').then(r => r.json()),
    fetch('data/mx_estados.topojson').then(r => r.json()),
  ]);
  S.meta = meta;
  S.ent = ent.years;
  S.geoEnt = topojson.feature(gEnt, gEnt.objects[Object.keys(gEnt.objects)[0]]);
  S.year = meta.anios[meta.anios.length - 1];
}

// carga perezosa de la capa municipal de un estado (datos + geometría)
export async function loadState(cve) {
  if (S.states[cve]) return S.states[cve];
  const [tasas, topo] = await Promise.all([
    fetch(`data/tasas_mun_${cve}.json`).then(r => r.json()),
    fetch(`data/mun_${cve}.topojson`).then(r => r.json()),
  ]);
  S.states[cve] = {
    years: tasas.years,
    geo: topojson.feature(topo,
      topo.objects[Object.keys(topo.objects)[0]]),
  };
  return S.states[cve];
}

const isMun = () => S.scope !== 'nacional';
export const dataset = () => (isMun() ? S.states[S.scope].years : S.ent);
export const record = (cvegeo, year = S.year) => dataset()[year]?.[cvegeo];
export const geojson = () => (isMun() ? S.states[S.scope].geo : S.geoEnt);
export const scopeName = () => isMun()
  ? (S.ent[S.year]?.[S.scope]?.n ?? `Estado ${S.scope}`) : 'México';
export const unitKind = () => (isMun() ? 'municipios' : 'entidades');

// valor de métrica vigente para una unidad
export function valueOf(rec) {
  if (!rec) return null;
  const c = rec.c[S.cohort] || rec.c.todas;
  if (S.metric === 'nac') return c[0];
  if (S.metric === 'tfr') return rec.tf ?? null;
  return S.smooth ? c[2] : c[1];   // tbn | tbs
}
export function nacOf(rec) { return rec?.c[S.cohort]?.[0] ?? rec?.v[0] ?? null; }
export function pobOf(rec) { return rec?.v[1] ?? null; }
export function flagOf(rec) { return rec?.f === 1; }
export function nombreOf(rec, cg) { return rec?.n || cg; }

// serie temporal de la unidad (métrica vigente)
export function seriesOf(cvegeo, scope = S.scope) {
  const ds = scope !== 'nacional' ? S.states[scope].years : S.ent;
  return S.meta.anios.map(y => {
    const r = ds[y]?.[cvegeo];
    if (!r) return null;
    if (S.metric === 'tfr') return r.tf ?? null;
    const c = r.c[S.cohort] || r.c.todas;
    return S.metric === 'nac' ? c[0] : (S.smooth ? c[2] : c[1]);
  });
}
// promedio de referencia: estatal para munis, nacional (00) para estados
export function refSeries() {
  return S.scope !== 'nacional' ? seriesOf(S.scope, 'nacional')
                                : seriesOf('00', 'nacional');
}
export const refName = () =>
  S.scope !== 'nacional' ? `Promedio ${scopeName()}` : 'Promedio nacional';

export function valuesOfYear(scope = S.scope, year = S.year) {
  const ds = scope !== 'nacional' ? S.states[scope].years : S.ent;
  const yr = ds[year] || {};
  const out = {};
  for (const [cg, rec] of Object.entries(yr)) out[cg] = valueOf(rec);
  return out;
}

export function percentile(cvegeo, scope = S.scope) {
  const vals = Object.entries(valuesOfYear(scope))
    .filter(([, v]) => v != null)
    .sort((a, b) => a[1] - b[1]);
  const i = vals.findIndex(([cg]) => cg === cvegeo);
  if (i < 0 || !vals.length) return null;
  return Math.round((i / (vals.length - 1)) * 100);
}

// un punto-ancla por unidad para etiquetas (evita duplicados de multipolígonos)
export function labelPoints() {
  const feats = [];
  for (const f of geojson().features) {
    const g = f.geometry;
    const polys = g.type === 'Polygon' ? [g.coordinates]
                : g.type === 'MultiPolygon' ? g.coordinates : [];
    let best = null, bestA = -1;
    for (const p of polys) {
      const ring = p[0];
      let a = 0;
      for (let i = 0; i < ring.length - 1; i++)
        a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1];
      if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = ring; }
    }
    if (!best) continue;
    let sx = 0, sy = 0;
    for (const [x, y] of best) { sx += x; sy += y; }
    feats.push({
      type: 'Feature',
      properties: { cvegeo: f.properties.cvegeo,
                    nombre: f.properties.nombre },
      geometry: { type: 'Point',
                  coordinates: [sx / best.length, sy / best.length] },
    });
  }
  return { type: 'FeatureCollection', features: feats };
}
