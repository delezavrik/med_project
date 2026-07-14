import type { AnswerResponse, ReviewExample } from "../api/types";
import { formatDuration } from "./RequestProgress";

interface Props {
  result: AnswerResponse | null;
}

const COLUMN_LABELS: Record<string, string> = {
  label: "Проблема",
  label_1: "Проблема 1",
  label_2: "Проблема 2",
  review_count: "Отзывы",
  share_pct: "Доля, %",
  period: "Период",
  count_period_1: "Было",
  count_period_2: "Стало",
  delta_abs: "Δ",
  delta_pct: "Δ, %",
  positive_count: "Положительные",
  problem_count: "Проблемные",
  problem_share_pct: "Доля проблем, %",
  product_id: "ID товара",
  product_name: "Товар",
  brand: "Бренд",
  category: "Категория",
  rating: "Рейтинг",
  date: "Дата",
  text: "Текст",
};

export function ResultView({ result }: Props) {
  if (!result) {
    return (
      <section className="panel result-panel empty-state">
        <p className="eyebrow">Результат</p>
        <h2>Запусти сценарий</h2>
        <p>Здесь появятся ответ, метрики, таблица и примеры отзывов.</p>
      </section>
    );
  }

  const rows = result.result.rows.map((row) => row.data);
  const examples = result.result.examples;
  const warnings = result.result.warnings;
  const duration = formatDuration(result.execution_ms);
  const shouldShowEmptyExamples = shouldShowTopProblemExamplesEmptyState(result);

  return (
    <section className="panel result-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Результат</p>
          <h2>{formatAnswerText(result.answer_text)}</h2>
        </div>
        <div className="result-meta">
          {duration && <span className="pill">время {duration}</span>}
          <span className="pill">{result.parsed_query.intent}</span>
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="alert warning">
          {warnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>
      )}

      {result.result.metrics.length > 0 && (
        <div className="metrics-row">
          {result.result.metrics.map((metric) => (
            <div className="metric-card" key={metric.name}>
              <span>{metric.name}</span>
              <strong>{formatValue(metric.value)}</strong>
              {metric.unit && <small>{metric.unit}</small>}
            </div>
          ))}
        </div>
      )}

      {rows.length > 0 && <DataTable rows={rows} />}
      {examples.length > 0 && <ReviewList examples={examples} />}
      {shouldShowEmptyExamples && <div className="alert">Примеры по выбранным фильтрам не найдены.</div>}

      {rows.length === 0 && examples.length === 0 && result.result.metrics.length === 0 && !shouldShowEmptyExamples && (
        <div className="alert">По выбранным фильтрам данных нет.</div>
      )}

      {result.trace_steps.length > 0 && <TraceSteps steps={result.trace_steps} />}

      <details className="debug-block">
        <summary>ParsedQuery и raw</summary>
        <pre>{JSON.stringify({ parsed_query: result.parsed_query, raw: result.result.raw }, null, 2)}</pre>
      </details>
    </section>
  );
}

function TraceSteps({ steps }: { steps: AnswerResponse["trace_steps"] }) {
  return (
    <section className="trace-panel">
      <div className="trace-header">
        <div>
          <p className="eyebrow">Ход выполнения</p>
          <h3>Макро-шаги запроса</h3>
        </div>
      </div>
      <div className="trace-list">
        {steps.map((step, index) => (
          <details className="trace-step" key={`${step.id}-${index}`}>
            <summary>
              <span>{index + 1}. {step.title}</span>
              <small>
                {step.status}
                {step.duration_ms !== null && step.duration_ms !== undefined ? ` · ${formatDuration(step.duration_ms)}` : ""}
              </small>
            </summary>
            <div className="trace-grid">
              <div>
                <strong>Вход</strong>
                <pre>{JSON.stringify(step.input, null, 2)}</pre>
              </div>
              <div>
                <strong>Выход</strong>
                <pre>{JSON.stringify(step.output, null, 2)}</pre>
              </div>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

function DataTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => <th key={column}>{COLUMN_LABELS[column] || column}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => <td key={column}>{formatCell(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReviewList({ examples }: { examples: ReviewExample[] }) {
  return (
    <div className="reviews-list">
      <h3>Примеры отзывов</h3>
      {examples.map((example) => (
        <article className="review-card" key={example.review_id || example.text}>
          <div className="review-meta">
            {example.date && <span>{example.date}</span>}
            {example.product_name && <span>{example.product_name}</span>}
            {!example.product_name && example.product_id && <span>ID товара {example.product_id}</span>}
            {example.product_name && example.product_id && <span>ID {example.product_id}</span>}
            {example.category && <span>{example.category}</span>}
            {example.brand && <span>{example.brand}</span>}
            {example.rating && <span>Рейтинг {example.rating}</span>}
          </div>
          <p>{example.text}</p>
          {example.labels.length > 0 && (
            <div className="tag-row">
              {example.labels.map((label) => <span className="tag" key={label}>{label}</span>)}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}

function shouldShowTopProblemExamplesEmptyState(result: AnswerResponse) {
  if (result.parsed_query.intent !== "top_problems" || result.parsed_query.examples_limit <= 0) {
    return false;
  }
  const metadata = result.result.raw.top_problem_examples;
  if (!metadata || typeof metadata !== "object") {
    return false;
  }
  const selectedCount = (metadata as { selected_count?: unknown }).selected_count;
  return result.result.examples.length === 0 && selectedCount === 0;
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function formatValue(value: number | string | null) {
  if (value === null) {
    return "-";
  }
  return String(value);
}

function formatAnswerText(value: string) {
  return value.split("**").join("");
}
