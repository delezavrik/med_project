import { type ReactNode } from "react";
import { KEY_BY_NAME, colByName, shortByName, fmt } from "./data";
import type { AnswerResponse, AResReview } from "./api";

// ---------- лёгкий markdown (bold + списки) ----------
function inline(s: string): ReactNode[] {
  return s.split("**").map((p, i) => (i % 2 === 1 ? <b key={i}>{p}</b> : <span key={i}>{p}</span>));
}
function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const out: ReactNode[] = [];
  let list: string[] = [];
  const flush = (k: number) => {
    if (list.length) { out.push(<ul key={"u" + k} style={{ margin: "4px 0 8px", paddingLeft: 18 }}>{list.map((li, j) => <li key={j} style={{ marginBottom: 3 }}>{inline(li)}</li>)}</ul>); list = []; }
  };
  lines.forEach((ln, i) => {
    const t = ln.trim();
    if (t.startsWith("- ") || t.startsWith("• ") || t.startsWith("* ")) list.push(t.slice(2));
    else { flush(i); if (t) out.push(<p key={i}>{inline(t)}</p>); }
  });
  flush(lines.length);
  return <>{out}</>;
}

function Stars({ n }: { n: number | null }) {
  if (!n) return null;
  return <span className="stars">{"★".repeat(n)}{"☆".repeat(5 - n)}</span>;
}

function ReviewCard({ r }: { r: AResReview }) {
  const labels = r.labels.filter((l) => KEY_BY_NAME[l]);
  return (
    <div className="rev">
      <div className="rh">
        {r.review_id && <span className="id">{r.review_id}</span>}
        <Stars n={r.rating} />
        {r.product_name && <span>{r.product_name}</span>}
        {r.date && <span>{r.date.slice(0, 10)}</span>}
        {r.score != null && <span style={{ marginLeft: "auto", color: "var(--accent)", fontWeight: 650 }}>score {r.score.toFixed(2)}</span>}
      </div>
      <p>«{r.text}»</p>
      {labels.length > 0 && (
        <div className="chips">
          {labels.map((l) => <span key={l} className="chip"><span className="sw" style={{ background: colByName(l) }} />{shortByName(l)}</span>)}
        </div>
      )}
    </div>
  );
}

// таблица label→count как бары (только канонические 9 меток)
function CountBars({ rows }: { rows: { data: Record<string, unknown> }[] }) {
  const items = rows
    .map((r) => ({ label: String(r.data.label ?? ""), count: Number(r.data.review_count ?? 0) }))
    .filter((i) => KEY_BY_NAME[i.label]);
  if (items.length === 0) return null;
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div className="ans-chart"><div className="bars">
      {items.map((i) => (
        <div key={i.label} className="bar-row" style={{ gridTemplateColumns: "190px 1fr 70px", cursor: "default" }}>
          <div className="bar-name"><span className="sw" style={{ background: colByName(i.label) }} /><span>{shortByName(i.label)}</span></div>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${(i.count / max * 100).toFixed(1)}%`, background: colByName(i.label) }} /></div>
          <div className="bar-val tnum">{fmt(i.count)}</div>
        </div>
      ))}
    </div></div>
  );
}

function GenericTable({ rows }: { rows: { data: Record<string, unknown> }[] }) {
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r.data)))).slice(0, 6);
  return (
    <div style={{ padding: "6px 15px 12px" }}><div className="tbl-wrap">
      <table className="tbl">
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.slice(0, 30).map((r, i) => (
            <tr key={i} style={{ cursor: "default" }}>{cols.map((c) => <td key={c}>{String(r.data[c] ?? "")}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div></div>
  );
}

export function AnswerView({ resp }: { resp: AnswerResponse }) {
  const { result, answer_text, answer_mode } = resp;
  const isLabelCount = result.rows.length > 0 && result.rows.every((r) => "label" in r.data && "review_count" in r.data);
  const showNarrative = answer_mode === "llm" && answer_text && !answer_text.startsWith("Найдено");

  return (
    <div className="answer">
      {showNarrative && <div className="lead"><Markdown text={answer_text} /></div>}

      {result.metrics.length > 0 && (
        <div className="ans-metrics">
          {result.metrics.map((m, i) => (
            <div key={i} className="ans-metric"><div className="l">{m.name}</div><div className="v">{m.value ?? "—"}{m.unit ? ` ${m.unit}` : ""}</div></div>
          ))}
        </div>
      )}

      {result.rows.length > 0 && (isLabelCount ? <CountBars rows={result.rows} /> : <GenericTable rows={result.rows} />)}

      {result.examples.length > 0 && (
        <>
          <div className="ans-block-h">
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 4h12M2 8h12M2 12h7" /></svg>
            Отзывы-подтверждения · {result.examples.length} шт. · с ID для проверки
          </div>
          <div className="ans-reviews">{result.examples.map((r, i) => <ReviewCard key={r.review_id ?? i} r={r} />)}</div>
        </>
      )}

      {result.warnings.length > 0 && (
        <div style={{ padding: "8px 17px 12px" }}>
          <div className="warnbar" style={{ margin: 0 }}><span className="ic">⚠</span><div>{result.warnings.map((w, i) => <div key={i}>{w}</div>)}</div></div>
        </div>
      )}

      {resp.trace_steps.length > 0 && (
        <details className="method" style={{ borderTop: "1px solid var(--border)" }}>
          <summary style={{ padding: "12px 17px" }}>
            <svg className="chev" width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M6 3l5 5-5 5" /></svg>
            <div className="t"><h3 style={{ fontSize: 13.5 }}>Как посчитано</h3></div>
            <span className="fact-tag" style={{ marginLeft: "auto" }}>шаги + SQL</span>
          </summary>
          <div style={{ padding: "0 17px 15px" }}>
            <div className="steps">
              {resp.trace_steps.map((s, i) => (
                <div key={i} className="step">
                  <span className="n">{i + 1}</span>
                  <div className="st">{s.title}<small>{Object.entries(s.output).map(([k, v]) => `${k}: ${v}`).join(" · ")}</small></div>
                  <span className="ms">{s.status}</span>
                </div>
              ))}
            </div>
          </div>
        </details>
      )}
    </div>
  );
}
