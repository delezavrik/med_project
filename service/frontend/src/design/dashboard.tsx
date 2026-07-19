import { useEffect, useRef, useState } from "react";
import { CMAP, col, cssv, fmt, pct, type ClassKey } from "./data";
import { fetchDashboard, type DashboardData, type Granularity } from "./api";
import { Sparkline, TopProblemsChart, DynamicsChart, PositiveVsProblem } from "./charts";
import type { QueryCtx } from "./answers";

interface DashProps {
  gran: Granularity;
  onDrill: (text: string, ctx: QueryCtx) => void;
  onChatSeed: (ctx: QueryCtx) => void;
  onChatAsk: (q: string, ctx?: QueryCtx) => void;
}

const fmtDate = (iso: string | null) => (iso ? iso.slice(8, 10) + "." + iso.slice(5, 7) : "");
const periodText = (d: DashboardData) => `${fmtDate(d.meta.period.date_from)}–${fmtDate(d.meta.period.date_to)}`;

// ---------- дельта-бейдж ----------
function Delta({ d, invert = false }: { d: number | null; invert?: boolean }) {
  if (d === null || d === undefined) return null;
  const good = invert ? d > 0 : d < 0;
  const cls = d === 0 ? "flat" : good ? "down" : "up";
  const arrow = d === 0 ? "→" : d > 0 ? "↑" : "↓";
  return <span className={"delta " + cls}>{arrow} {Math.abs(d)}%</span>;
}

// ---------- Сводка ----------
function SummaryBand({ data, onChatSeed, onChatAsk, onDyn }: {
  data: DashboardData; onChatSeed: (ctx: QueryCtx) => void; onChatAsk: (q: string, ctx?: QueryCtx) => void; onDyn: () => void;
}) {
  const neg = data.metrics.find((m) => m.name === "Доля негатива");
  const grow = data.metrics.find((m) => m.name === "Самая растущая проблема");
  const growKey = (grow?.label_key ?? undefined) as ClassKey | undefined;
  const topP = data.problems[0];
  return (
    <section>
      <div className="summary">
        <div className="badge">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 2a10 10 0 1 0 10 10" /><path d="M12 7v5l3 2" /></svg>
        </div>
        <div className="body">
          <div className="line">
            За <b>{periodText(data)}</b> проблема есть у <b>{typeof neg?.value === "number" ? pct(neg.value, 1) : neg?.value}</b> отзывов.
            {grow && grow.delta_pct !== null && topP && growKey === topP.label_key ? (
              <> Главная и одновременно растущая проблема — <b className="hot">{topP.short.toLowerCase()}: {pct(topP.share * 100, 1)} отзывов, +{grow.delta_pct}%</b> к прошлому периоду. С неё и стоит начать.</>
            ) : (
              <>
                {grow && grow.delta_pct !== null ? <> Резче всего растёт <b className="hot">{String(grow.value).toLowerCase()} (+{grow.delta_pct}%)</b> — с неё и стоит начать.</> : null}
                {topP ? <> Самая частая — <b>{topP.short.toLowerCase()} ({pct(topP.share * 100, 1)})</b>.</> : null}
              </>
            )}
          </div>
          <div className="acts">
            {growKey && (
              <button className="btn primary" onClick={() => onChatSeed({ intent: "problem_growth_analysis", label: growKey })}>
                Разобраться с ростом
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M3 8h9M8 4l4 4-4 4" /></svg>
              </button>
            )}
            <button className="btn" onClick={() => onChatAsk("Что сильнее всего выросло к прошлому периоду?", { intent: "growth" })}>Что ещё выросло</button>
            <button className="btn" onClick={onDyn}>Показать динамику</button>
          </div>
          <div className="updated">Данные из PostgreSQL · расчёт {data.meta.execution_ms} мс</div>
        </div>
      </div>
    </section>
  );
}

// ---------- KPI ----------
function KpiRow({ data }: { data: DashboardData }) {
  const neg = data.metrics.find((m) => m.name === "Доля негатива");
  const grow = data.metrics.find((m) => m.name === "Самая растущая проблема");
  const periods = data.metrics.find((m) => m.name === "Период данных");
  const growKey = (grow?.label_key ?? undefined) as ClassKey | undefined;
  const growSpark = growKey ? data.series.by_label[growKey] || [] : [];
  return (
    <div className="kpis">
      <div className="kpi">
        <div className="lab">Всего отзывов</div>
        <div className="val tnum">{fmt(data.meta.total_reviews)}</div>
        <div className="foot"><span>за период</span></div>
        <Sparkline vals={data.series.negative_share} stroke={cssv("--ink-3")} fill={cssv("--ink-3")} />
      </div>
      <div className="kpi">
        <div className="lab">Доля негатива</div>
        <div className="val tnum">{typeof neg?.value === "number" ? neg.value.toLocaleString("ru-RU") : neg?.value} <small>%</small></div>
        <div className="foot"><Delta d={neg?.delta_pct ?? null} /><span>к пред. периоду</span></div>
        <Sparkline vals={data.series.negative_share} stroke={cssv("--critical")} fill={cssv("--critical")} />
      </div>
      <div className="kpi">
        <div className="lab">Самая растущая проблема</div>
        <div className="val tnum" style={{ color: growKey ? col(growKey) : undefined }}>{grow?.delta_pct !== null && grow?.delta_pct !== undefined ? `+${grow.delta_pct}%` : "—"}</div>
        <div className="foot"><span>{grow?.value}</span></div>
        {growSpark.length > 0 && growKey && <Sparkline vals={growSpark} stroke={col(growKey)} fill={col(growKey)} />}
      </div>
      <div className="kpi">
        <div className="lab">Период данных</div>
        <div className="val tnum">{periods?.value} <small>{periods?.unit}</small></div>
        <div className="foot"><span>{data.meta.period.date_from?.slice(0, 10)} – {data.meta.period.date_to?.slice(0, 10)}</span></div>
      </div>
    </div>
  );
}

// ---------- Алерты ----------
function AlertsCard({ data, onDrill }: { data: DashboardData; onDrill: (text: string, ctx: QueryCtx) => void }) {
  const rows = data.problems.slice().sort((a, b) => (b.delta_pct ?? -999) - (a.delta_pct ?? -999));
  return (
    <section className="card">
      <div className="card-h"><div className="t"><h3>На что смотреть сейчас</h3><div className="sub">рост к прошлому равному периоду</div></div></div>
      <div className="card-b">
        <div className="alerts">
          {rows.map((c) => (
            <div
              key={c.label_key} className="alert-row" tabIndex={0}
              onClick={() => onDrill(`Рост «${c.short}» ${c.delta_pct !== null ? (c.delta_pct > 0 ? "+" : "") + c.delta_pct + "%" : ""}`, { intent: "problem_growth_analysis", label: c.label_key })}
              onKeyDown={(e) => { if (e.key === "Enter") onDrill(`Рост «${c.short}»`, { intent: "problem_growth_analysis", label: c.label_key }); }}
            >
              <div className="an"><span className="sw" style={{ background: col(c.label_key) }} />{c.short}</div>
              <span style={{ justifySelf: "end" }}><Delta d={c.delta_pct} /></span>
              <div className="asub">{fmt(c.count)} отзывов · {pct(c.share * 100, 1)} от всех</div>
              <div className="amini"><Sparkline vals={c.spark} stroke={col(c.label_key)} fill={col(c.label_key)} /></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------- Товары ----------
function ProductsCard({ data, onDrill }: { data: DashboardData; onDrill: (text: string, ctx: QueryCtx) => void }) {
  if (data.top_products.length === 0) {
    return (
      <section className="card">
        <div className="card-h"><div className="t"><h3>Товары с наибольшим риском</h3><div className="sub">доля проблемных отзывов и главная проблема</div></div></div>
        <div className="card-b"><div className="empty" style={{ padding: "28px 20px" }}><p>Недостаточно отзывов по конкретным товарам за период, чтобы построить рейтинг риска.</p></div></div>
      </section>
    );
  }
  return (
    <section className="card">
      <div className="card-h"><div className="t"><h3>Товары с наибольшим риском</h3><div className="sub">доля проблемных отзывов и главная проблема</div></div></div>
      <div className="card-b" style={{ paddingTop: 8 }}>
        <div className="tbl-wrap">
          <table className="tbl">
            <thead><tr><th>Товар</th><th className="r">Отзывов</th><th>Главные проблемы</th><th className="r">Риск</th></tr></thead>
            <tbody>
              {data.top_products.map((p) => {
                const rc = p.risk_score >= 65 ? cssv("--critical") : p.risk_score >= 45 ? cssv("--serious") : cssv("--warning");
                return (
                  <tr key={p.product_id} onClick={() => onDrill(`Товар «${p.product_name}»`, { intent: "product_summary", product: p.product_name })}>
                    <td><b style={{ fontWeight: 600 }}>{p.product_name}</b><div style={{ color: "var(--ink-3)", fontSize: 11.5 }}>{p.brand || "—"}</div></td>
                    <td className="r tnum">{fmt(p.total)}</td>
                    <td><div className="chips">{p.top_labels.map((k) => <span key={k} className="chip"><span className="sw" style={{ background: col(k) }} />{CMAP[k]?.short ?? k}</span>)}</div></td>
                    <td className="r"><span className="risk"><span className="rt"><i style={{ width: `${p.risk_score}%`, background: rc }} /></span><b className="tnum" style={{ color: rc }}>{p.risk_score}</b></span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

// ---------- «Как посчитано» ----------
function MethodPanel({ data }: { data: DashboardData }) {
  return (
    <details className="card method">
      <summary>
        <svg className="chev" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M6 3l5 5-5 5" /></svg>
        <div className="t"><h3>Как это посчитано</h3><div className="sub">шаги расчёта из реальной базы — чтобы проверить, а не поверить</div></div>
        <span className="fact-tag" style={{ marginLeft: "auto" }}>● Факт из БД</span>
      </summary>
      <div className="method-b">
        <div className="steps">
          {data.trace_steps.map((s, i) => (
            <div key={s.id} className="step">
              <span className="n">{i + 1}</span>
              <div className="st">{s.title}<small>{Object.entries(s.output).map(([k, v]) => `${k}: ${v}`).join(" · ")}</small></div>
              <span className="ms">{s.status}</span>
            </div>
          ))}
        </div>
        <div className="note">Числа — факт из PostgreSQL по 9 каноническим классам. Объяснения и примеры отзывов доступны в чате: кликните проблему на графике.</div>
      </div>
    </details>
  );
}

// ---------- предупреждения ----------
function WarningsBar({ data }: { data: DashboardData }) {
  const [hidden, setHidden] = useState(false);
  const items = data.warnings.filter((w) => w.code !== "empty");
  if (hidden || items.length === 0) return null;
  return (
    <div className="warnbar">
      <span className="ic">⚠</span>
      <div>{items.map((w, i) => <div key={i}>{w.message}</div>)}</div>
      <button className="x" onClick={() => setHidden(true)}>✕</button>
    </div>
  );
}

// ---------- состояния ----------
function LoadingDash() {
  return (
    <main className="dash">
      <div className="summary"><div className="skl" style={{ width: 38, height: 38, borderRadius: 10, flex: "none" }} /><div style={{ flex: 1 }}><div className="skl" style={{ height: 18, width: "82%" }} /><div className="skl" style={{ height: 18, width: "54%", marginTop: 9 }} /></div></div>
      <div className="kpis">{[0, 1, 2, 3].map((i) => <div key={i} className="kpi"><div className="skl" style={{ height: 14, width: "60%" }} /><div className="skl" style={{ height: 28, width: "80%" }} /><div className="skl" style={{ height: 26 }} /></div>)}</div>
      <section className="card"><div className="card-h"><div className="t"><h3>Динамика проблем</h3></div></div><div className="card-b">
        <div className="skl" style={{ height: 240 }} />
        <div className="load-steps">
          <div className="load-step done"><span className="dot" />Отбираем отзывы по фильтрам</div>
          <div className="load-step done"><span className="dot" />Читаем метки классификатора</div>
          <div className="load-step run"><span className="dot" />Считаем доли и динамику…</div>
          <div className="load-step"><span className="dot" />Сравниваем с прошлым периодом</div>
        </div>
      </div></section>
    </main>
  );
}

// ---------- главный вид ----------
export function DashboardView({ gran, onDrill, onChatSeed, onChatAsk }: DashProps) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const dynRef = useRef<HTMLElement>(null);
  const scrollDyn = () => dynRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });

  function load() {
    setStatus("loading");
    let cancelled = false;
    fetchDashboard(gran)
      .then((d) => { if (!cancelled) { setData(d); setStatus("ready"); } })
      .catch(() => { if (!cancelled) setStatus("error"); });
    return () => { cancelled = true; };
  }
  useEffect(load, [gran]);

  if (status === "loading") return <LoadingDash />;
  if (status === "error") {
    return (
      <main className="dash">
        <section className="card"><div className="card-b"><div className="empty">
          <svg className="ill" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: "var(--critical)" }}><path d="M12 3l9 16H3z" /><path d="M12 10v4M12 17v.5" /></svg>
          <h3>Не удалось загрузить данные</h3>
          <p>Сервис аналитики сейчас недоступен. Проверьте, запущен ли бэкенд, и попробуйте снова.</p>
          <div className="acts"><button className="btn primary" onClick={load}>Повторить</button></div>
        </div></div></section>
      </main>
    );
  }
  if (!data || data.meta.total_reviews === 0) {
    return (
      <main className="dash">
        <section className="card"><div className="card-b"><div className="empty">
          <svg className="ill" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="11" cy="11" r="7" /><path d="M16 16l5 5" /></svg>
          <h3>Нет отзывов по фильтрам</h3>
          <p>За выбранный период и фильтры отзывов не нашлось. Попробуйте расширить период или убрать фильтр.</p>
        </div></div></section>
      </main>
    );
  }

  return (
    <main className="dash">
      <SummaryBand data={data} onChatSeed={onChatSeed} onChatAsk={onChatAsk} onDyn={scrollDyn} />
      <WarningsBar data={data} />
      <KpiRow data={data} />

      <div className="row a">
        <section className="card">
          <div className="card-h">
            <div className="t"><h3>Топ проблем и доли</h3><div className="sub">доля отзывов с проблемой · за выбранный период</div></div>
            <div className="tools"><span className="fact-tag">● Факт из БД</span></div>
          </div>
          <div className="card-b">
            <TopProblemsChart positive={data.positive} problems={data.problems} onDrill={(k) => onDrill(`Проблема «${CMAP[k]?.short ?? k}»`, { intent: "review_examples", label: k })} />
          </div>
        </section>
        <AlertsCard data={data} onDrill={onDrill} />
      </div>

      <section className="card" ref={dynRef}>
        <div className="card-h">
          <div className="t"><h3>Динамика проблем во времени</h3><div className="sub">доля отзывов с проблемой, % · {{ day: "по дням", week: "по неделям", month: "по месяцам" }[gran]}</div></div>
          <div className="tools"><span className="fact-tag">● Факт из БД</span></div>
        </div>
        <div className="card-b">
          <DynamicsChart buckets={data.meta.buckets} negativeShare={data.series.negative_share} byLabel={data.series.by_label} problems={data.problems} />
        </div>
      </section>

      <div className="row b">
        <ProductsCard data={data} onDrill={onDrill} />
        <section className="card">
          <div className="card-h"><div className="t"><h3>Позитив и проблемы</h3><div className="sub">структура отзывов по периодам, %</div></div></div>
          <div className="card-b"><PositiveVsProblem buckets={data.meta.buckets} positiveShare={data.positive_vs_problem.positive_share} /></div>
        </section>
      </div>

      <MethodPanel data={data} />
    </main>
  );
}
