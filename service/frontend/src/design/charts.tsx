import { useState } from "react";
import {
  CLASSES, CMAP, SERIES, WEEKS, negShareSeries,
  col, cssv, fmt, pct, type ClassKey,
} from "./data";
import type { DashProblem } from "./api";
import { showTip, hideTip, tipRow } from "./tip";

// ---------- Sparkline (KPI / алерты) ----------
export function Sparkline({ vals, stroke, fill }: { vals: number[]; stroke: string; fill?: string }) {
  const w = 120, h = 26, pad = 2;
  if (!vals.length) return <svg className="spark" viewBox={`0 0 ${w} ${h}`} />;
  const mn = Math.min(...vals), mx = Math.max(...vals), rng = mx - mn || 1;
  const pt = (v: number, i: number) => {
    const x = pad + (i * (w - 2 * pad)) / Math.max(1, vals.length - 1);
    const y = h - pad - ((v - mn) / rng) * (h - 2 * pad);
    return [x, y] as const;
  };
  const d = vals.map((v, i) => { const [x, y] = pt(v, i); return (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1); }).join(" ");
  const [lx, ly] = pt(vals[vals.length - 1], vals.length - 1);
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      {fill && <path d={`${d} L ${w - 2} ${h - 2} L 2 ${h - 2} Z`} fill={fill} opacity={0.14} />}
      <path d={d} fill="none" stroke={stroke} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lx} cy={ly} r={2.4} fill={stroke} />
    </svg>
  );
}

// ---------- Топ проблем: горизонтальные бары (данные с бэка) ----------
export function TopProblemsChart(
  { positive, problems, onDrill }: {
    positive: { short: string; share: number };
    problems: DashProblem[];
    onDrill: (key: ClassKey) => void;
  },
) {
  const max = Math.max(...problems.map((p) => p.share), 0.0001);
  return (
    <div>
      <div className="pos-strip">
        <span className="bar-name" style={{ width: "auto" }}>
          <span className="sw" style={{ background: col("pos") }} />{positive.short}
        </span>
        <span className="barmini"><i style={{ width: `${(positive.share * 100).toFixed(0)}%` }} /></span>
        <b className="tnum" style={{ fontSize: 13 }}>{pct(positive.share * 100, 0)}</b>
      </div>
      <div className="bars">
        {problems.map((p) => {
          const deltaTxt = p.delta_pct === null ? "—" : (p.delta_pct > 0 ? "+" : "") + p.delta_pct + "%";
          return (
            <div
              key={p.label_key} className="bar-row" tabIndex={0}
              onMouseMove={(e) => showTip(
                `<div class="th">${p.label}</div>${tipRow(col(p.label_key), "Отзывов", fmt(p.count))}${tipRow(col(p.label_key), "Доля от всех", pct(p.share * 100, 1))}${tipRow(col(p.label_key), "Δ к периоду", deltaTxt)}`,
                e.clientX, e.clientY)}
              onMouseLeave={hideTip}
              onClick={() => onDrill(p.label_key)}
              onKeyDown={(e) => { if (e.key === "Enter") onDrill(p.label_key); }}
            >
              <div className="bar-name"><span className="sw" style={{ background: col(p.label_key) }} /><span>{p.short}</span></div>
              <div className="bar-track"><div className="bar-fill" style={{ width: `${(p.share / max * 100).toFixed(1)}%`, background: col(p.label_key) }} /></div>
              <div className="bar-val tnum">{pct(p.share * 100, 1)}<small>{fmt(p.count)} шт.</small></div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------- Динамика: мультилайн с переключаемой легендой (данные с бэка) ----------
export function DynamicsChart(
  { buckets, negativeShare, byLabel, problems }: {
    buckets: string[];
    negativeShare: number[];
    byLabel: Record<string, number[]>;
    problems: DashProblem[];
  },
) {
  const topKeys = problems.slice().sort((a, b) => b.share - a.share).slice(0, 3).map((p) => p.label_key);
  const [hidden, setHidden] = useState<Set<string>>(
    () => new Set(problems.filter((p) => !topKeys.includes(p.label_key)).map((p) => p.label_key)),
  );
  const toggle = (k: string) => setHidden((prev) => { const n = new Set(prev); if (n.has(k)) n.delete(k); else n.add(k); return n; });

  const N = buckets.length;
  const W = 860, H = 280, m = { l: 34, r: 56, t: 14, b: 26 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const shown = problems.filter((p) => !hidden.has(p.label_key));
  const seriesOf = (k: string) => byLabel[k] || [];
  const maxV = Math.max(Math.max(...negativeShare, 0), ...shown.flatMap((p) => seriesOf(p.label_key)), 1) * 1.12;
  const denom = Math.max(1, N - 1);
  const x = (i: number) => m.l + (i * iw) / denom;
  const y = (v: number) => m.t + ih - (v / maxV) * ih;
  const grid = cssv("--grid"), ink3 = cssv("--ink-3"), ink2 = cssv("--ink-2");
  const negD = negativeShare.map((v, i) => (i ? "L" : "M") + x(i) + " " + y(v)).join(" ");
  const hitW = iw / denom;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ overflow: "visible" }} role="img">
        {[0, 1, 2, 3, 4].map((g) => {
          const gv = (maxV * g) / 4, gy = y(gv);
          return (
            <g key={g}>
              <line x1={m.l} y1={gy} x2={m.l + iw} y2={gy} stroke={grid} strokeWidth={1} />
              <text x={m.l - 8} y={gy + 3} textAnchor="end" fontSize={10.5} fill={ink3}>{gv.toFixed(0)}</text>
            </g>
          );
        })}
        {buckets.map((w, i) => (i % 2 === 0 || i === N - 1) && (
          <text key={w + i} x={x(i)} y={H - 8} textAnchor="middle" fontSize={10.5} fill={ink3}>{w}</text>
        ))}
        <path d={negD} fill="none" stroke={ink2} strokeWidth={2.4} strokeDasharray="1 5" strokeLinecap="round" opacity={0.75} />
        {shown.map((p) => {
          const s = seriesOf(p.label_key);
          const d = s.map((v, i) => (i ? "L" : "M") + x(i) + " " + y(v)).join(" ");
          const ly = y(s[s.length - 1] ?? 0);
          return (
            <g key={p.label_key}>
              <path d={d} fill="none" stroke={col(p.label_key)} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />
              <circle cx={x(N - 1)} cy={ly} r={3} fill={col(p.label_key)} />
              <text x={x(N - 1) + 7} y={ly + 3.5} fontSize={10.5} fontWeight={700} fill={col(p.label_key)}>{(s[s.length - 1] ?? 0).toFixed(1)}</text>
            </g>
          );
        })}
        {buckets.map((w, i) => (
          <rect
            key={"h" + w + i} x={x(i) - hitW / 2} y={m.t} width={hitW} height={ih} fill="transparent"
            onMouseMove={(e) => {
              let rows = tipRow(ink2, "Всего негатив", pct(negativeShare[i] ?? 0, 1));
              shown.forEach((p) => { rows += tipRow(col(p.label_key), p.short, pct(seriesOf(p.label_key)[i] ?? 0, 1)); });
              showTip(`<div class="th">${w}</div>${rows}`, e.clientX, e.clientY);
            }}
            onMouseLeave={hideTip}
          />
        ))}
      </svg>
      <div className="legend">
        <button disabled style={{ opacity: 0.9 }}><span className="sw" style={{ background: ink2 }} />Всего негатив</button>
        {problems.map((p) => (
          <button key={p.label_key} className={hidden.has(p.label_key) ? "off" : ""} onClick={() => toggle(p.label_key)}>
            <span className="sw" style={{ background: col(p.label_key) }} />{p.short}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------- Позитив vs проблемы (данные с бэка) ----------
export function PositiveVsProblem({ buckets, positiveShare }: { buckets: string[]; positiveShare: number[] }) {
  const N = buckets.length;
  const W = 420, H = 210, m = { l: 28, r: 10, t: 12, b: 22 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const denom = Math.max(1, N - 1);
  const x = (i: number) => m.l + (i * iw) / denom;
  const y = (v: number) => m.t + ih - (v / 100) * ih;
  const grid = cssv("--grid"), ink3 = cssv("--ink-3"), crit = cssv("--critical"), posc = col("pos");
  const posArea = "M" + x(0) + " " + y(0) + " " + positiveShare.map((v, i) => "L" + x(i) + " " + y(v)).join(" ") + " L" + x(N - 1) + " " + y(0) + " Z";
  const negArea = "M" + x(0) + " " + y(100) + " " + positiveShare.map((v, i) => "L" + x(i) + " " + y(v)).join(" ") + " L" + x(N - 1) + " " + y(100) + " Z";
  const hitW = iw / denom;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ overflow: "visible" }} role="img">
        {[0, 25, 50, 75, 100].map((g) => (
          <g key={g}>
            <line x1={m.l} y1={y(g)} x2={m.l + iw} y2={y(g)} stroke={grid} />
            <text x={m.l - 6} y={y(g) + 3} textAnchor="end" fontSize={10} fill={ink3}>{g}</text>
          </g>
        ))}
        <path d={negArea} fill={crit} opacity={0.16} />
        <path d={posArea} fill={posc} opacity={0.18} />
        <path d={positiveShare.map((v, i) => (i ? "L" : "M") + x(i) + " " + y(v)).join(" ")} fill="none" stroke={posc} strokeWidth={2.4} strokeLinecap="round" />
        {buckets.map((w, i) => (
          <rect
            key={w + i} x={x(i) - hitW / 2} y={m.t} width={hitW} height={ih} fill="transparent"
            onMouseMove={(e) => showTip(`<div class="th">${w}</div>${tipRow(posc, "Позитив / нейтрал", pct(positiveShare[i] ?? 0, 0))}${tipRow(crit, "С проблемой", pct(100 - (positiveShare[i] ?? 0), 0))}`, e.clientX, e.clientY)}
            onMouseLeave={hideTip}
          />
        ))}
      </svg>
      <div className="legend" style={{ paddingTop: 10 }}>
        <button disabled style={{ opacity: 0.9 }}><span className="sw" style={{ background: posc }} />Позитив / нейтрал</button>
        <button disabled style={{ opacity: 0.9 }}><span className="sw" style={{ background: crit }} />Есть проблема</button>
      </div>
    </div>
  );
}

// ============================================================
//  Ниже — компоненты для чата/сценариев (пока на демо-данных)
// ============================================================

export function MiniLine({ keyName }: { keyName: ClassKey | "__neg" }) {
  const isNeg = keyName === "__neg";
  const vals = isNeg ? negShareSeries : SERIES[keyName];
  const color = isNeg ? cssv("--ink-2") : col(keyName);
  const label = isNeg ? "Всего негатив" : CMAP[keyName].short;
  const W = 560, H = 150, m = { l: 26, r: 40, t: 10, b: 20 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const mx = Math.max(...vals) * 1.15;
  const x = (i: number) => m.l + (i * iw) / (WEEKS.length - 1);
  const y = (v: number) => m.t + ih - (v / mx) * ih;
  const grid = cssv("--grid"), ink3 = cssv("--ink-3");
  const d = vals.map((v, i) => (i ? "L" : "M") + x(i) + " " + y(v)).join(" ");
  const hitW = iw / (WEEKS.length - 1);
  const ly = y(vals[vals.length - 1]);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ overflow: "visible" }}>
      {[0, 1, 2, 3].map((g) => {
        const gy = y((mx * g) / 3);
        return (
          <g key={g}>
            <line x1={m.l} y1={gy} x2={m.l + iw} y2={gy} stroke={grid} />
            <text x={m.l - 6} y={gy + 3} textAnchor="end" fontSize={10} fill={ink3}>{((mx * g) / 3).toFixed(0)}</text>
          </g>
        );
      })}
      {WEEKS.map((w, i) => (i % 3 === 0 || i === WEEKS.length - 1) && (
        <text key={w} x={x(i)} y={H - 6} textAnchor="middle" fontSize={9.5} fill={ink3}>{w}</text>
      ))}
      <path d={`${d} L${x(WEEKS.length - 1)} ${y(0)} L${x(0)} ${y(0)} Z`} fill={color} opacity={0.13} />
      <path d={d} fill="none" stroke={color} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={x(WEEKS.length - 1)} cy={ly} r={3} fill={color} />
      <text x={x(WEEKS.length - 1) + 6} y={ly + 3.5} fontSize={10.5} fontWeight={700} fill={color}>{vals[vals.length - 1].toFixed(1)}</text>
      {WEEKS.map((w, i) => (
        <rect
          key={"h" + w} x={x(i) - hitW / 2} y={m.t} width={hitW} height={ih} fill="transparent"
          onMouseMove={(e) => showTip(`<div class="th">Неделя ${w}</div>${tipRow(color, label, pct(vals[i], 1))}`, e.clientX, e.clientY)}
          onMouseLeave={hideTip}
        />
      ))}
    </svg>
  );
}

export function MiniBars(
  { rows, signed, onPick }: { rows: typeof CLASSES; signed?: boolean; onPick?: (k: ClassKey) => void },
) {
  const max = Math.max(...rows.map((r) => (signed ? Math.abs(r.delta) : r.share)));
  return (
    <div className="bars">
      {rows.map((r) => {
        const w = (signed ? Math.abs(r.delta) : r.share) / max * 100;
        const c = signed ? (r.delta > 0 ? cssv("--critical") : cssv("--good")) : col(r.key);
        return (
          <div
            key={r.key} className="bar-row" tabIndex={0}
            style={{ gridTemplateColumns: "160px 1fr 58px" }}
            onClick={() => onPick?.(r.key)}
          >
            <div className="bar-name"><span className="sw" style={{ background: col(r.key) }} /><span>{r.short}</span></div>
            <div className="bar-track"><div className="bar-fill" style={{ width: `${w.toFixed(1)}%`, background: c }} /></div>
            <div className="bar-val tnum">{signed ? (r.delta > 0 ? "+" : "") + r.delta + "%" : pct(r.share * 100, 1)}</div>
          </div>
        );
      })}
    </div>
  );
}

export function PreviewLine({ keyName }: { keyName: ClassKey | "__neg" }) {
  const vals = keyName === "__neg" ? negShareSeries : SERIES[keyName];
  const color = keyName === "__neg" ? cssv("--ink-2") : col(keyName);
  const W = 200, H = 54, mx = Math.max(...vals) * 1.12, mn = Math.min(...vals) * 0.86, rng = mx - mn || 1;
  const x = (i: number) => 4 + (i * (W - 8)) / (vals.length - 1);
  const y = (v: number) => H - 5 - ((v - mn) / rng) * (H - 12);
  const d = vals.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1)).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" preserveAspectRatio="none">
      <path d={`${d} L${x(vals.length - 1).toFixed(1)} ${H} L${x(0)} ${H} Z`} fill={color} opacity={0.13} />
      <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
export function PreviewBars({ keys, signed }: { keys: ClassKey[]; signed?: boolean }) {
  const data = keys.map((k) => ({ k, v: signed ? Math.abs(CMAP[k].delta) : CMAP[k].share }));
  const mx = Math.max(...data.map((d) => d.v)) || 1;
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 7, width: "100%", height: "100%" }}>
      {data.map((d) => (
        <div key={d.k} style={{ flex: 1, height: `${(d.v / mx * 100).toFixed(0)}%`, minHeight: 5, background: col(d.k), borderRadius: "3px 3px 0 0" }} />
      ))}
    </div>
  );
}
export function PreviewDots() {
  const rows: [ClassKey, number][] = [["pack", 0.9], ["pack", 0.72], ["card", 0.58]];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%" }}>
      {rows.map(([k, w], i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: col(k), flex: "none" }} />
          <span style={{ flex: 1, height: 7, borderRadius: 999, background: "var(--surface-3)", overflow: "hidden" }}>
            <i style={{ display: "block", height: "100%", width: `${w * 100}%`, background: "var(--accent)", opacity: 0.55 }} />
          </span>
        </div>
      ))}
    </div>
  );
}
