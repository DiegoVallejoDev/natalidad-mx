// map.js — MapLibre: coropleta, tooltips, drill-down, indicador de varianza
import { S, geojson, labelPoints, valuesOfYear, record, valueOf, nacOf, pobOf,
         flagOf, nombreOf, percentile } from './data.js';
import { classify, stepExpr, fmtBreak, fmtNum } from './classify.js';
import { onSelect, drillToJalisco } from './app.js';

let map = null;
let hoverCve = null;
const SRC = 'units', SRC_LAB = 'labels-src';
const LYR_FILL = 'fill', LYR_OUT = 'outline', LYR_SEL = 'sel',
      LYR_FLAG = 'flaglines', LYR_LAB = 'labels';

function baseStyle() {
  return {
    version: 8,
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources: {},
    layers: [{ id: 'bg', type: 'background',
               paint: { 'background-color': '#0d1117' } }],
  };
}

export function initMap() {
  map = new maplibregl.Map({
    container: 'map',
    style: baseStyle(),
    center: [-102.5, 23.8],
    zoom: 4.2,
    maxZoom: 12,
    minZoom: 3,
    attributionControl: { compact: true },
    preserveDrawingBuffer: true,
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }),
                 'top-right');
  map.addControl(new maplibregl.ScaleControl(), 'bottom-right');
  map.on('load', () => {
    addScopeLayers(map);
    wireEvents(map);
    refreshValues(map);
    onSelect();
  });
  return map;
}

function addScopeLayers(m) {
  for (const l of [LYR_FILL, LYR_OUT, LYR_SEL, LYR_FLAG, LYR_LAB])
    if (m.getLayer(l)) m.removeLayer(l);
  if (m.getSource(SRC)) m.removeSource(SRC);
  if (m.getSource(SRC_LAB)) m.removeSource(SRC_LAB);

  m.addSource(SRC, {
    type: 'geojson', data: geojson(), promoteId: 'cvegeo',
  });
  m.addSource(SRC_LAB, { type: 'geojson', data: labelPoints() });
  m.addLayer({
    id: LYR_FILL, type: 'fill', source: SRC,
    paint: { 'fill-color': '#3a4658', 'fill-opacity': 0.92 },
  });
  m.addLayer({
    id: LYR_OUT, type: 'line', source: SRC,
    paint: {
      'line-color': '#1b2436',
      'line-width': S.scope === 'jalisco' ? 0.4 : 1.0,
    },
  });
  // alta varianza (P<10k): contorno punteado ámbar — RF-03.1
  m.addLayer({
    id: LYR_FLAG, type: 'line', source: SRC,
    paint: {
      'line-color': ['case', ['==', ['feature-state', 'flag'], true],
                     '#f0b429', 'rgba(0,0,0,0)'],
      'line-width': ['case', ['==', ['feature-state', 'flag'], true], 1.3, 0],
      'line-dasharray': [2, 2],
    },
  });
  m.addLayer({
    id: LYR_SEL, type: 'line', source: SRC,
    paint: {
      'line-color': ['case', ['==', ['feature-state', 'sel'], true],
                     '#58a6ff', 'rgba(0,0,0,0)'],
      'line-width': ['case', ['==', ['feature-state', 'sel'], true], 2.5, 0],
    },
  });
  m.addLayer({
    id: LYR_LAB, type: 'symbol', source: SRC_LAB,
    layout: {
      'text-field': ['get', 'nombre'],
      'text-size': S.scope === 'jalisco' ? 9 : 11,
      'text-font': ['Open Sans Semibold'],
      'symbol-placement': 'point',
      'text-max-width': 8,
    },
    paint: {
      'text-color': '#dfe7f3',
      'text-halo-color': '#0d1117',
      'text-halo-width': 1.4,
      'text-opacity': S.scope === 'jalisco'
        ? ['interpolate', ['linear'], ['zoom'], 6.4, 0, 7.2, 0.9] : 0.9,
    },
  });
}

function wireEvents(m) {
  m.on('mousemove', LYR_FILL, e => {
    m.getCanvas().style.cursor = 'pointer';
    const f = e.features?.[0];
    if (!f) return;
    hoverCve = f.properties.cvegeo;
    showTip(e.originalEvent, hoverCve);
  });
  m.on('mouseleave', LYR_FILL, () => {
    m.getCanvas().style.cursor = '';
    hoverCve = null;
    hideTip();
  });
  m.on('click', LYR_FILL, e => {
    const f = e.features?.[0];
    if (!f) return;
    const cg = f.properties.cvegeo;
    if (S.scope === 'nacional' && cg === '14') { drillToJalisco(); return; }
    selectUnit(cg);
  });
}

export function selectUnit(cg) {
  const prev = S.selected;
  S.selected = (S.selected === cg) ? null : cg;
  for (const old of [prev, S.selected]) {
    if (old) {
      try { map.setFeatureState({ source: SRC, id: old },
                                { sel: old === S.selected }); } catch (_) {}
    }
  }
  onSelect();
}

// recalcula cortes + pinta vía feature-state — O(unidades visibles)
export function refreshValues(m = map) {
  if (!m || !m.getSource(SRC)) return;
  const vals = valuesOfYear();
  const { breaks, colors } = classify(Object.values(vals), S.klass);
  m.setPaintProperty(LYR_FILL, 'fill-color', stepExpr(breaks, colors));
  for (const f of geojson().features) {
    const cg = f.properties.cvegeo;
    const rec = record(cg);
    m.setFeatureState({ source: SRC, id: cg }, {
      v: valueOf(rec),
      flag: flagOf(rec) && S.scope === 'jalisco',
      sel: cg === S.selected,
    });
  }
  if (m === map) {
    renderLegend(breaks, colors);
    hideTip();
    document.getElementById('varnote').classList.toggle('hidden',
      !(S.scope === 'jalisco' &&
        geojson().features.some(f => flagOf(record(f.properties.cvegeo)))));
  }
}

function renderLegend(breaks, colors) {
  const lg = document.getElementById('legend');
  if (!colors.length) { lg.innerHTML = ''; return; }
  const vals = Object.values(valuesOfYear())
    .filter(v => v != null).sort((a, b) => a - b);
  const lo = vals[0] ?? 0;
  const names = { jenks: 'Jenks', quantile: 'Cuantiles',
                  equal: 'Intervalos iguales', stddev: 'Desv. estándar' };
  const titles = { tbn: 'TBN por 1,000 hab.',
                   tfr: 'TFR (hijos por mujer)',
                   nac: 'Nacimientos' };
  let rows = `<div class="lg-title">${
    titles[S.metric]} · ${names[S.klass]}</div>`;
  let prev = lo;
  colors.forEach((c, i) => {
    const hi = breaks[i];
    const label = hi == null ? `> ${fmtBreak(prev, S.metric)}`
      : (prev === hi ? `${fmtBreak(hi, S.metric)}`
        : `${fmtBreak(prev, S.metric)} – ${fmtBreak(hi, S.metric)}`);
    rows += `<div class="lg-row"><span class="lg-swatch"
      style="background:${c}"></span><span class="lg-range">${label}</span></div>`;
    prev = hi;
  });
  lg.innerHTML = rows;
}

function showTip(ev, cg) {
  const tip = document.getElementById('tip');
  const rec = record(cg);
  const v = valueOf(rec), pct = percentile(cg);
  const metricName = { nac: 'Nacimientos',
                       tfr: 'TFR (hijos/mujer)' }[S.metric]
    || (S.smooth ? 'TBN suavizada ‰' : 'TBN ‰');
  const reemplazo = S.metric === 'tfr' && v != null
    ? (v < 2.1
      ? '<div class="tip-warn">⚠ Bajo nivel de reemplazo (&lt; 2.1)</div>'
      : '<div class="tip-pct">Sobre nivel de reemplazo (≥ 2.1)</div>')
    : '';
  tip.innerHTML = `
    <h3>${nombreOf(rec, cg)}</h3>
    <div class="tip-cve">CVEGEO ${cg}</div>
    <table>
      <tr><td>${metricName}</td><td>${fmtNum(v, S.metric === 'nac' ? 0 : 2)}</td></tr>
      <tr><td>Nacimientos</td><td>${fmtNum(nacOf(rec), 0)}</td></tr>
      <tr><td>Población base</td><td>${fmtNum(pobOf(rec), 0)}</td></tr>
    </table>
    ${reemplazo}
    ${flagOf(rec) ? '<div class="tip-warn">⚠ Alta varianza: población ' +
      '&lt; 10,000 — considere la media trienal</div>' : ''}
    ${pct != null ? `<div class="tip-pct">Percentil ${pct} ${
      S.scope === 'jalisco' ? 'de Jalisco' : 'nacional'}</div>` : ''}`;
  tip.classList.remove('hidden');
  const pane = document.querySelector('.map-pane');
  const r = pane.getBoundingClientRect();
  let x = ev.clientX - r.left + 14, y = ev.clientY - r.top + 14;
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  if (x + tw > r.width - 8) x = ev.clientX - r.left - tw - 14;
  if (y + th > r.height - 8) y = ev.clientY - r.top - th - 14;
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}
function hideTip() { document.getElementById('tip').classList.add('hidden'); }

export function switchScope(scope) {
  S.scope = scope;
  S.selected = null;
  hideTip();
  addScopeLayers(map);
  const onData = e => {
    if (e.sourceId === SRC && e.isSourceLoaded) {
      map.off('sourcedata', onData);
      refreshValues(map);
    }
  };
  map.on('sourcedata', onData);
  if (scope === 'jalisco') {
    map.fitBounds([[-104.75, 18.85], [-101.2, 21.9]], { padding: 30 });
  } else {
    map.fitBounds([[-118.5, 14.3], [-86.5, 32.9]], { padding: 20 });
  }
}

// PNG ~300 DPI: mapa temporal oculto con pixelRatio alto, mismo estilo
export function captureHiResPNG() {
  return new Promise((resolve, reject) => {
    const host = document.getElementById('map');
    const tmp = document.createElement('div');
    tmp.style.cssText = `position:fixed;left:-10000px;top:0;` +
      `width:${host.clientWidth}px;height:${host.clientHeight}px`;
    document.body.appendChild(tmp);
    const tm = new maplibregl.Map({
      container: tmp, style: baseStyle(), pixelRatio: 3,
      interactive: false, attributionControl: false,
      preserveDrawingBuffer: true,
    });
    tm.on('load', () => {
      addScopeLayers(tm);
      const onData = e => {
        if (e.sourceId === SRC && e.isSourceLoaded) {
          tm.off('sourcedata', onData);
          refreshValues(tm);
          tm.jumpTo({ center: map.getCenter(), zoom: map.getZoom(),
                      bearing: map.getBearing(), pitch: map.getPitch() });
          tm.once('idle', () => {
            const url = tm.getCanvas().toDataURL('image/png');
            tm.remove();
            tmp.remove();
            resolve(url);
          });
        }
      };
      tm.on('sourcedata', onData);
    });
    tm.on('error', err => { tmp.remove(); reject(err); });
  });
}
export const getMap = () => map;
