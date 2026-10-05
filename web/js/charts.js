// charts.js — ECharts: serie temporal, histograma+KDE, dispersión, ranking
import { S, seriesOf, refSeries, refName, valuesOfYear, record,
         nombreOf, flagOf, valueOf } from './data.js';
import { fmtNum } from './classify.js';

const PAL = { a: '#58a6ff', b: '#f0b429', c: '#3fb950',
              grid: '#22304a', text: '#8b949e' };
const charts = {};

function mk(id) {
  if (!charts[id]) charts[id] = echarts.init(document.getElementById(id));
  return charts[id];
}
const baseAxis = () => ({
  axisLine: { lineStyle: { color: PAL.grid } },
  axisLabel: { color: PAL.text, fontSize: 10 },
  splitLine: { lineStyle: { color: PAL.grid, opacity: .4 } },
});

export function updateSeries() {
  const c = mk('ch-series');
  const yrs = S.meta.anios;
  const sel = S.selected ? seriesOf(S.selected) : null;
  const ref = refSeries();
  const selName = S.selected
    ? nombreOf(record(S.selected), S.selected) : '—';
  document.getElementById('ts-tag').textContent =
    `${selName} vs. ${refName()}`;
  c.setOption({
    animationDuration: 250,
    grid: { left: 44, right: 12, top: 26, bottom: 22 },
    tooltip: { trigger: 'axis',
      valueFormatter: v => fmtNum(v, S.metric === 'nac' ? 0 : 2) },
    legend: { textStyle: { color: PAL.text, fontSize: 10 }, top: 0,
              itemWidth: 14 },
    xAxis: { type: 'category', data: yrs, ...baseAxis() },
    yAxis: { type: 'value', scale: true, ...baseAxis() },
    series: [
      sel && {
        name: selName, type: 'line', data: sel, smooth: true,
        lineStyle: { color: PAL.a, width: 2.5 },
        itemStyle: { color: PAL.a },
        areaStyle: { color: PAL.a, opacity: .12 },
        symbolSize: 5,
      },
      { name: refName(), type: 'line', data: ref, smooth: true,
        lineStyle: { color: PAL.b, width: 1.8, type: 'dashed' },
        itemStyle: { color: PAL.b }, symbolSize: 4 },
    ].filter(Boolean),
  }, true);
}

// RF-04.2a — histograma + KDE de la TBN municipal de Jalisco
export function updateDist() {
  const c = mk('ch-dist');
  const vals = Object.values(valuesOfYear('jalisco'))
    .filter(v => v != null);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const nb = 18, w = (hi - lo) / nb || 1;
  const bins = Array.from({ length: nb }, (_, i) => ({
    x: lo + w * (i + .5), n: 0 }));
  vals.forEach(v => bins[Math.min(nb - 1, Math.floor((v - lo) / w))].n++);
  // KDE gaussiano, bw Silverman
  const sd = ss.sampleStandardDeviation(vals) || 1;
  const bw = 1.06 * sd * Math.pow(vals.length, -.2);
  const xs = Array.from({ length: 80 }, (_, i) => lo + (hi - lo) * i / 79);
  const kde = xs.map(x => vals.reduce((acc, v) =>
    acc + Math.exp(-0.5 * ((x - v) / bw) ** 2), 0)
    / (vals.length * bw * Math.sqrt(2 * Math.PI)));
  const maxK = Math.max(...kde) || 1;
  const maxB = Math.max(...bins.map(b => b.n)) || 1;
  c.setOption({
    animationDuration: 250,
    grid: { left: 36, right: 12, top: 26, bottom: 22 },
    tooltip: { trigger: 'axis' },
    xAxis: [
      { type: 'category',
        data: bins.map(b => fmtNum(b.x, 1)), ...baseAxis(),
        axisLabel: { color: PAL.text, fontSize: 9, interval: 3 },
        name: S.metric === 'nac' ? 'nac.' : '‰',
        nameTextStyle: { color: PAL.text } },
      { type: 'value', min: lo, max: hi, show: false },
    ],
    yAxis: { type: 'value', ...baseAxis() },
    series: [
      { name: 'municipios', type: 'bar', barWidth: '92%',
        data: bins.map(b => b.n), itemStyle: { color: PAL.a, opacity: .55 } },
      { name: 'KDE', type: 'line', xAxisIndex: 1,
        smooth: true, symbol: 'none',
        data: xs.map((x, i) => [x, kde[i] / maxK * maxB]),
        lineStyle: { color: PAL.b, width: 2 } },
    ],
  }, true);
}

// RF-04.2b — dispersión TBN vs población (log)
export function updateScatter() {
  const c = mk('ch-scatter');
  const yr = S.mun[S.year] || {};
  const pts = Object.entries(yr).map(([cg, r]) => ({
    v: [r.v[1], valueOf(r)],
    name: `${nombreOf(r, cg)} (${cg})`,
    flag: flagOf(r), sel: cg === S.selected,
  })).filter(p => p.v[1] != null && p.v[0] > 0);
  c.setOption({
    animationDuration: 250,
    grid: { left: 52, right: 12, top: 26, bottom: 30 },
    tooltip: { trigger: 'item',
      formatter: p => `${p.data.name}<br/>pob: ${fmtNum(p.data.value[0], 0)}` +
        `<br/>valor: ${fmtNum(p.data.value[1], 2)}` +
        (p.data.flag ? '<br/>⚠ alta varianza' : '') },
    xAxis: { type: 'log', name: 'población (log)', ...baseAxis(),
             nameTextStyle: { color: PAL.text } },
    yAxis: { type: 'value', scale: true, ...baseAxis() },
    series: [{
      type: 'scatter',
      data: pts.map(p => ({
        value: p.v, name: p.name, flag: p.flag, sel: p.sel,
        itemStyle: { color: p.sel ? '#ff6b6b' : (p.flag ? PAL.b : PAL.a),
                     opacity: p.sel ? 1 : .7 },
        symbolSize: p.sel ? 11 : 6,
      })),
    }],
  }, true);
}

// RF-04.3 — ranking top/bottom 10 Jalisco
export function updateRank() {
  const c = mk('ch-rank');
  const yr = S.mun[S.year] || {};
  const rows = Object.entries(yr)
    .map(([cg, r]) => ({ cg, v: valueOf(r), n: nombreOf(r, cg) }))
    .filter(r => r.v != null)
    .sort((a, b) => a.v - b.v);
  const top = rows.slice(-10), bot = rows.slice(0, 10);
  const data = [...bot, ...top];
  c.setOption({
    animationDuration: 250,
    grid: { left: 118, right: 30, top: 8, bottom: 20 },
    tooltip: { trigger: 'item',
      formatter: p => `${data[p.dataIndex].n}<br/>${fmtNum(data[p.dataIndex].v, 2)}` },
    xAxis: { type: 'value', ...baseAxis() },
    yAxis: {
      type: 'category',
      data: data.map(r => `${r.n}`),
      ...baseAxis(),
      axisLabel: { color: PAL.text, fontSize: 9.5, width: 110,
                   overflow: 'truncate' },
    },
    series: [{
      type: 'bar',
      data: data.map((r, i) => ({
        value: r.v,
        itemStyle: { color: i < 10 ? PAL.c : '#d29922',
                     opacity: r.cg === S.selected ? 1 : .75 },
      })),
      barWidth: '65%',
      label: { show: true, position: 'right', color: PAL.text,
               fontSize: 9, formatter: p => fmtNum(p.value, 1) },
    }],
  }, true);
}

export function updateMeta() {
  const el = document.getElementById('meta-info');
  const m = S.meta;
  el.innerHTML = `
    <div class="mrow"><span>Fuente nacimientos</span><b>SINAC · ocurrencia</b></div>
    <div class="mrow"><span>Población</span><b>CONAPO mitad de año</b></div>
    <div class="mrow"><span>Serie</span><b>${m.anios[0]}–${m.anios[m.anios.length - 1]}</b></div>
    <div class="mrow"><span>Excluidos extranjero</span><b>${fmtNum(m.exclusiones.EXTRANJERO || 0, 0)}</b></div>
    <div class="mrow"><span>No especificado</span><b>${fmtNum(m.exclusiones.NO_ESPECIFICADO || 0, 0)}</b></div>
    <div style="margin-top:6px">Cobertura SINAC ≈ 86–90% del registro civil (nacimientos en unidades de salud). Las claves de residencia corresponden a la madre. Click en Jalisco para drill-down municipal.</div>`;
}

export function updateAll() {
  updateSeries(); updateDist(); updateScatter(); updateRank();
}

export function resizeAll() {
  Object.values(charts).forEach(c => c.resize());
}

export function svgExports() {
  // renderToSVGString solo existe en instancias con renderer SVG
  return Object.entries(charts).map(([id, c]) => {
    const tmp = document.createElement('div');
    tmp.style.cssText = 'position:absolute;left:-9999px;width:640px;height:360px';
    document.body.appendChild(tmp);
    const sc = echarts.init(tmp, null, { renderer: 'svg' });
    sc.setOption(c.getOption());
    const svg = sc.renderToSVGString();
    sc.dispose();
    tmp.remove();
    return { id, svg };
  });
}
