// classify.js — métodos de clasificación de cortes + rampa perceptual
// Viridis (perceptualmente uniforme, segura para daltonismo)
const VIRIDIS = [
  '#440154', '#48186a', '#472f7d', '#424086', '#3b528b', '#33638d',
  '#2c728e', '#26828e', '#21918c', '#1fa088', '#28ae80', '#3fbc73',
  '#5ec962', '#84d44b', '#addc30', '#d8e219', '#fde725',
];
const NCLASSES = 6;

function ramp(i, n = NCLASSES) {
  return VIRIDIS[Math.round(i * (VIRIDIS.length - 1) / (n - 1))];
}

// devuelve {breaks:[b1..b5], colors:[c0..c5]} — b_i = límite superior de clase i
export function classify(values, method) {
  const v = values.filter(x => x != null && isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return { breaks: [], colors: [] };
  const colors = Array.from({ length: NCLASSES }, (_, i) => ramp(i));
  let breaks;
  if (method === 'quantile') {
    breaks = [];
    for (let i = 1; i < NCLASSES; i++)
      breaks.push(ss.quantile(v, i / NCLASSES));
  } else if (method === 'equal') {
    const [lo, hi] = [v[0], v[v.length - 1]];
    breaks = [];
    for (let i = 1; i < NCLASSES; i++)
      breaks.push(lo + (hi - lo) * i / NCLASSES);
  } else if (method === 'stddev') {
    const mean = ss.mean(v), sd = ss.sampleStandardDeviation(v);
    // clases centradas en la media ±0.5σ, ±1σ…, truncadas al dominio
    const raw = [mean - 2.5 * sd, mean - 1.5 * sd, mean - 0.5 * sd,
                 mean + 0.5 * sd, mean + 1.5 * sd, mean + 2.5 * sd];
    breaks = raw.filter(b => b > v[0] && b < v[v.length - 1]);
  } else { // jenks
    const res = ss.ckmeans(v.slice(), NCLASSES);
    breaks = res.slice(0, -1).map(g => g[g.length - 1]);
  }
  // dedup + orden (evita cortes degenerados con distribuciones atípicas)
  breaks = [...new Set(breaks.map(b => +b.toFixed(6)))].sort((a, b) => a - b);
  return { breaks: breaks.slice(0, NCLASSES - 1), colors };
}

// expresión maplibre para colorear por feature-state 'v'
export function stepExpr(breaks, colors) {
  const expr = ['step', ['feature-state', 'v'], colors[0]];
  breaks.forEach((b, i) => expr.push(b, colors[i + 1]));
  return [
    'case',
    ['==', ['feature-state', 'v'], null], '#3a4658',   // sin datos
    expr,
  ];
}

export function fmtNum(v, dec = 1) {
  if (v == null) return '—';
  return v.toLocaleString('es-MX',
    { maximumFractionDigits: dec, minimumFractionDigits: 0 });
}
export function fmtBreak(b, metric) {
  if (metric === 'nac') return fmtNum(b, 0);
  if (metric === 'tfr') return fmtNum(b, 2);
  return fmtNum(b, 1);
}
