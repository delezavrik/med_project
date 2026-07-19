import {
  CLASSES, CMAP, PROBLEMS, PRODUCTS, METHOD_REVIEWS, NEG_SHARE, negShareSeries,
  col, cssv, fmt, pct, TOTAL,
  type ClassKey, type ClassDef, type ProductRow, type ReviewItem,
} from "./data";
import { MiniLine, MiniBars } from "./charts";

// ---------- модель ответа ----------
export interface AnswerMetric { l: string; v: string; c?: string; delta?: boolean; deltaVal?: number; }
export interface AnswerFollow { t: string; q: string; }
export type ChartSpec =
  | { kind: "line"; keyName: ClassKey | "__neg" }
  | { kind: "bars"; rows: ClassDef[]; signed?: boolean };

export interface AnswerSpec {
  ms?: string;
  lead: string[];
  hyp?: string;
  metrics?: AnswerMetric[];
  chart?: ChartSpec;
  table?: ProductRow[];
  reviews?: ReviewItem[];
  reviewsLabel?: string;
  trace?: [string, string, string][];
  follow?: AnswerFollow[];
}

export interface QueryCtx { intent?: string; label?: ClassKey; product?: string; }

// ---------- генераторы ----------
export function ansPackaging(): AnswerSpec {
  return {
    ms: "71 мс",
    lead: ["Жалобы на <b>комплектацию / упаковку</b> выросли на <b>+34%</b> к прошлому равному периоду — это самый резкий рост среди всех классов. Сейчас это <b>7,1%</b> всех отзывов (3 431 шт.)."],
    hyp: "Рост почти целиком дал бренд <b>NORDWAY</b> (пуховики): всплеск пришёлся на партии второй половины сентября. Похоже на проблему упаковки на стороне поставки, а не самого товара — почти во всех отзывах товар оценивают нормально, претензия к пакету/коробке.",
    metrics: [
      { l: "Доля сейчас", v: "7,1%", c: col("pack") },
      { l: "Рост к периоду", v: "+34%", c: cssv("--critical"), delta: true, deltaVal: 34 },
      { l: "Отзывов", v: "3 431" },
    ],
    chart: { kind: "line", keyName: "pack" },
    reviewsLabel: "3 отзыва-подтверждения",
    reviews: METHOD_REVIEWS,
    trace: [
      ["Отобрал отзывы с меткой «упаковка»", "период + предыдущий период", "11 мс"],
      ["Сгруппировал по бренду и неделе", "GROUP BY brand, week", "23 мс"],
      ["Достал 3 примера", "по свежести и уверенности метки", "RAG"],
    ],
    follow: [
      { t: "Показать по неделям", q: "Как менялась доля жалоб на упаковку по неделям?" },
      { t: "Топ товаров с упаковкой", q: "Топ товаров с проблемой упаковки" },
      { t: "Похожие отзывы", q: "Покажи похожие отзывы про плохую упаковку" },
    ],
  };
}
export function ansGrowth(): AnswerSpec {
  const rows = PROBLEMS.slice().sort((a, b) => b.delta - a.delta).slice(0, 4);
  return {
    ms: "44 мс",
    lead: ["За период сильнее всего выросли: " + rows.filter((r) => r.delta > 0).map((r) => `<b>${r.short}</b> (${r.delta > 0 ? "+" : ""}${r.delta}%)`).join(", ") + ". Реагировать в первую очередь стоит на упаковку — рост и объём одновременно высокие."],
    metrics: rows.slice(0, 3).map((r) => ({ l: r.short, v: (r.delta > 0 ? "+" : "") + r.delta + "%", c: col(r.key), delta: true, deltaVal: r.delta })),
    chart: { kind: "bars", rows, signed: true },
    trace: [
      ["Посчитал доли за оба периода", "текущий и предыдущий равный", "29 мс"],
      ["Вычислил дельты", "(тек − пред)/пред", "8 мс"],
    ],
    follow: [
      { t: "Почему выросла упаковка?", q: "Почему выросли жалобы на упаковку?" },
      { t: "Динамика по неделям", q: "Как менялась доля жалоб на упаковку по неделям?" },
    ],
  };
}
export function ansTop(): AnswerSpec {
  const rows = PROBLEMS.slice().sort((a, b) => b.share - a.share).slice(0, 5);
  return {
    ms: "38 мс",
    lead: ["Главные проблемы периода: " + rows.slice(0, 3).map((r) => `<b>${r.short}</b> (${pct(r.share * 100, 1)})`).join(", ") + ". Позитивных / нейтральных отзывов — 58,1%."],
    metrics: [
      { l: "Проблемных отзывов", v: pct(NEG_SHARE, 1), c: cssv("--critical") },
      { l: "Главная проблема", v: rows[0].short.split(" ")[0], c: col(rows[0].key) },
    ],
    chart: { kind: "bars", rows },
    trace: [
      ["Отобрал отзывы по фильтрам", "48 320", "12 мс"],
      ["Свернул по меткам", "GROUP BY label", "26 мс"],
    ],
    follow: [
      { t: "Что из этого растёт?", q: "Что сильнее всего выросло к прошлому периоду?" },
      { t: "Товары с риском", q: "Топ товаров с проблемой упаковки" },
    ],
  };
}
export function ansDynamics(): AnswerSpec {
  return {
    ms: "40 мс",
    lead: [`Доля отзывов с проблемой держится около <b>${pct(NEG_SHARE, 0)}</b> и медленно растёт. Основной вклад в рост — упаковка и качество; размер, наоборот, снижается.`],
    metrics: [
      { l: "Сейчас", v: pct(negShareSeries[negShareSeries.length - 1], 1), c: cssv("--critical") },
      { l: "12 недель назад", v: pct(negShareSeries[0], 1) },
    ],
    chart: { kind: "line", keyName: "__neg" },
    trace: [
      ["Свернул отзывы по неделям", "date_trunc(week, review_date)", "26 мс"],
      ["Посчитал долю негатива", "COUNT(DISTINCT review_id) с проблемой / все", "12 мс"],
    ],
    follow: [
      { t: "Что именно растёт?", q: "Что сильнее всего выросло к прошлому периоду?" },
      { t: "Почему упаковка?", q: "Почему выросли жалобы на упаковку?" },
    ],
  };
}
export function ansCompare(): AnswerSpec {
  const rows = PROBLEMS.slice().sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 5);
  return {
    ms: "51 мс",
    lead: ["Сравнение с прошлым равным периодом. Выросли: упаковка +34%, возврат +18%, качество +12%. Снизились: размер −6%, доставка −1%."],
    metrics: [
      { l: "Доля негатива", v: pct(NEG_SHARE, 1), c: cssv("--critical"), delta: true, deltaVal: 3 },
      { l: "Было", v: "40,7%" },
    ],
    chart: { kind: "bars", rows, signed: true },
    trace: [
      ["Определил предыдущий период", "та же длина, встык", "4 мс"],
      ["Посчитал обе выборки", "параллельно", "40 мс"],
      ["Дельты по классам", "", "7 мс"],
    ],
    follow: [{ t: "Почему выросла упаковка?", q: "Почему выросли жалобы на упаковку?" }],
  };
}
export function ansProducts(): AnswerSpec {
  const rows = PRODUCTS.filter((p) => p.top.includes("pack")).concat(PRODUCTS.filter((p) => !p.top.includes("pack"))).slice(0, 4);
  return {
    ms: "47 мс",
    lead: ["Товары, где проблема упаковки встречается чаще всего. Верх списка — <b>Пуховик оверсайз</b> (NORDWAY): 27% отзывов с упоминанием упаковки."],
    table: rows,
    trace: [
      ["Отфильтровал по метке «упаковка»", "", "9 мс"],
      ["Свернул по товарам", "GROUP BY product", "31 мс"],
    ],
    follow: [{ t: "Отзывы по пуховику", q: "Покажи отзывы с проблемой упаковки и объясни суть" }],
  };
}
export function ansRag(): AnswerSpec {
  return {
    ms: "1,8 с",
    lead: ["Нашёл отзывы, близкие по смыслу к «плохая упаковка» (векторный поиск BGE-M3, не по точному слову). Ниже — самые релевантные."],
    hyp: "Смысловые кластеры: «порвана/помята упаковка при доставке» и «нет заявленной комплектации». Второе — ближе к несоответствию карточке, чем к самой упаковке.",
    reviewsLabel: "Похожие отзывы · score",
    reviews: METHOD_REVIEWS.map((r, i) => ({ ...r, score: (0.89 - i * 0.06).toFixed(2) })),
    trace: [
      ["Построил эмбеддинг запроса", "BGE-M3", "1,4 с"],
      ["Искал в Qdrant", "top-3, cosine", "120 мс"],
      ["Достал тексты из Postgres", "по review_id", "18 мс"],
    ],
    follow: [{ t: "Сколько таких всего?", q: "Как менялась доля жалоб на упаковку по неделям?" }],
  };
}
export function ansLabel(key: ClassKey): AnswerSpec {
  const c = CMAP[key];
  const revs = METHOD_REVIEWS.filter((r) => r.labels.includes(key));
  return {
    ms: "40 мс",
    lead: [`Проблема «<b>${c.short}</b>»: ${pct(c.share * 100, 1)} всех отзывов (${fmt(Math.round(c.share * TOTAL))} шт.), изменение ${c.delta > 0 ? "+" : ""}${c.delta}% к прошлому периоду.`],
    metrics: [
      { l: "Доля", v: pct(c.share * 100, 1), c: col(key) },
      { l: "Отзывов", v: fmt(Math.round(c.share * TOTAL)) },
      { l: "Δ период", v: (c.delta > 0 ? "+" : "") + c.delta + "%", c: c.delta > 0 ? cssv("--critical") : cssv("--good"), delta: true, deltaVal: c.delta },
    ],
    chart: { kind: "line", keyName: key },
    reviewsLabel: "Примеры отзывов",
    reviews: revs.length ? revs : METHOD_REVIEWS.slice(0, 2),
    trace: [["Отобрал отзывы с меткой", "", "10 мс"], ["Достал примеры", "", "8 мс"]],
    follow: [
      { t: "Динамика", q: `Как менялась доля «${c.short}» по неделям?` },
      { t: "Товары", q: `Топ товаров с проблемой ${c.short}` },
    ],
  };
}

export function route(text: string, ctx: QueryCtx = {}): AnswerSpec {
  const t = (text || "").toLowerCase();
  const key = ctx.intent;
  if (key === "rag" || /похож/.test(t)) return ansRag();
  if (key === "products" || /товар/.test(t)) return ansProducts();
  if (key === "compare" || /сравн/.test(t)) return ansCompare();
  if (key === "top" || /топ проблем|главн/.test(t)) return ansTop();
  if (/упаков|комплект/.test(t) || ctx.label === "pack") return ansPackaging();
  if (key === "growth" || key === "dyn" || /вырос|рост|динамик/.test(t)) return ansGrowth();
  if (ctx.label) return ansLabel(ctx.label);
  return ansTop();
}

// ---------- отрисовка ----------
export function ReviewCard({ r }: { r: ReviewItem }) {
  const stars = "★".repeat(r.rating) + "☆".repeat(5 - r.rating);
  return (
    <div className="rev">
      <div className="rh">
        <span className="id">{r.id}</span>
        <span className="stars">{stars}</span>
        <span>{r.prod}</span>
        {r.score && <span style={{ marginLeft: "auto", color: "var(--accent)", fontWeight: 650 }}>score {r.score}</span>}
      </div>
      <p>«{r.text}»</p>
      <div className="chips">
        {r.labels.map((k) => (
          <span key={k} className="chip"><span className="sw" style={{ background: col(k) }} />{CMAP[k].short}</span>
        ))}
      </div>
    </div>
  );
}

export function AnswerTable({ rows, onPick }: { rows: ProductRow[]; onPick?: (name: string) => void }) {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead><tr><th>Товар</th><th className="r">Отзывов</th><th>Проблемы</th><th className="r">Риск</th></tr></thead>
        <tbody>
          {rows.map((p) => {
            const rc = p.risk >= 65 ? cssv("--critical") : p.risk >= 45 ? cssv("--serious") : cssv("--warning");
            return (
              <tr key={p.name} onClick={() => onPick?.(p.name)}>
                <td><b style={{ fontWeight: 600 }}>{p.name}</b><div style={{ color: "var(--ink-3)", fontSize: 11.5 }}>{p.brand}</div></td>
                <td className="r tnum">{fmt(p.total)}</td>
                <td><div className="chips">{p.top.map((k) => <span key={k} className="chip"><span className="sw" style={{ background: col(k) }} />{CMAP[k].short}</span>)}</div></td>
                <td className="r"><b className="tnum" style={{ color: rc }}>{p.risk}</b></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function AnswerCard(
  { spec, onAsk }: { spec: AnswerSpec; onAsk: (q: string, ctx?: QueryCtx) => void },
) {
  return (
    <div className="answer">
      <div className="lead">
        {spec.lead.map((p, i) => <p key={i} dangerouslySetInnerHTML={{ __html: p }} />)}
        {spec.hyp && (
          <div className="hyp-line">
            <span className="fact-tag hyp tag">◇ Гипотеза</span>
            <span dangerouslySetInnerHTML={{ __html: spec.hyp }} />
          </div>
        )}
      </div>

      {spec.metrics && spec.metrics.length > 0 && (
        <div className="ans-metrics">
          {spec.metrics.map((m, i) => (
            <div key={i} className="ans-metric">
              <div className="l">{m.l}</div>
              <div className="v" style={m.c ? { color: m.c } : undefined}>
                {m.v}
                {m.delta && (
                  <span className={"delta " + (m.deltaVal! > 0 ? "up" : m.deltaVal! < 0 ? "down" : "flat")} style={{ fontSize: 11 }}>
                    {m.deltaVal! > 0 ? "↑" : m.deltaVal! < 0 ? "↓" : "→"} {Math.abs(m.deltaVal || 0)}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {spec.chart && (
        <div className="ans-chart">
          {spec.chart.kind === "line"
            ? <MiniLine keyName={spec.chart.keyName} />
            : <MiniBars rows={spec.chart.rows} signed={spec.chart.signed} onPick={(k) => onAsk(`Покажи отзывы с проблемой «${CMAP[k].short}» и объясни суть`, { label: k })} />}
        </div>
      )}

      {spec.table && (
        <>
          <div className="ans-block-h"><span className="fact-tag">● Факт из БД</span> Товары</div>
          <div style={{ padding: "6px 15px 12px" }}>
            <AnswerTable rows={spec.table} onPick={(name) => onAsk(`Какие главные проблемы у товара «${name}»?`, { product: name })} />
          </div>
        </>
      )}

      {spec.reviews && spec.reviews.length > 0 && (
        <>
          <div className="ans-block-h">
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 4h12M2 8h12M2 12h7" /></svg>
            {spec.reviewsLabel || "Отзывы-подтверждения"} · с ID для проверки
          </div>
          <div className="ans-reviews">{spec.reviews.map((r) => <ReviewCard key={r.id} r={r} />)}</div>
        </>
      )}

      {spec.trace && spec.trace.length > 0 && (
        <details className="method" style={{ borderTop: "1px solid var(--border)" }}>
          <summary style={{ padding: "12px 17px" }}>
            <svg className="chev" width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M6 3l5 5-5 5" /></svg>
            <div className="t"><h3 style={{ fontSize: 13.5 }}>Как посчитано</h3></div>
            <span className="fact-tag" style={{ marginLeft: "auto" }}>шаги + SQL</span>
          </summary>
          <div style={{ padding: "0 17px 15px" }}>
            <div className="steps">
              {spec.trace.map((s, i) => (
                <div key={i} className="step">
                  <span className="n">{i + 1}</span>
                  <div className="st">{s[0]}{s[1] && <small>{s[1]}</small>}</div>
                  <span className="ms">{s[2]}</span>
                </div>
              ))}
            </div>
          </div>
        </details>
      )}

      {spec.follow && spec.follow.length > 0 && (
        <div className="followups" style={{ padding: "12px 15px 15px" }}>
          {spec.follow.map((f, i) => (
            <button key={i} className="followup" onClick={() => onAsk(f.q)}>{f.t}</button>
          ))}
        </div>
      )}
    </div>
  );
}
