import { useState, type FormEvent } from "react";
import { askChat } from "../api/client";
import type { AnswerResponse } from "../api/types";
import { RequestProgress } from "../components/RequestProgress";
import { ResultView } from "../components/ResultView";
import {
  createHistoryEntry,
  loadHistory,
  RequestHistory,
  saveHistory,
  type HistoryEntry,
} from "../components/RequestHistory";

const EXAMPLES = [
  "Какие главные проблемы у книг в сентябре?",
  "Покажи динамику жалоб на упаковку по неделям",
  "Были ли отзывы про рваные обложки в сентябре?",
  "Найди отзывы, где есть фраза \"порвана упаковка\"",
  "Покажи похожие отзывы про плохую упаковку",
  "Что сильнее всего выросло в октябре?",
];

export function ChatAnalyticsPage() {
  const [message, setMessage] = useState(EXAMPLES[0]);
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forceSummary, setForceSummary] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>(() => loadHistory());

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (!message.trim()) {
      setError("Введите вопрос.");
      return;
    }

    setLoading(true);
    setStartedAt(Date.now());
    try {
      const response = await askChat({ message: message.trim(), force_answer_mode: forceSummary ? "llm" : null });
      setResult(response);
      addHistoryEntry(createHistoryEntry("chat", message.trim(), response));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  function addHistoryEntry(entry: HistoryEntry) {
    setHistory((previous) => {
      const next = [entry, ...previous].slice(0, 30);
      saveHistory(next);
      return next;
    });
  }

  function clearHistory() {
    setHistory([]);
    saveHistory([]);
  }

  const estimate = estimateChatWait(message, forceSummary);

  return (
    <main className="workspace">
      <section className="intro">
        <p className="eyebrow">Чат с аналитиком</p>
        <h1>Свободный вопрос к отзывам</h1>
        <p>Чат сначала пробует LLM parser, а без API-ключа использует rule-based fallback.</p>
      </section>

      <div className="layout">
        <div className="stack">
          <form className="panel form-panel" onSubmit={handleSubmit}>
            <div className="panel-header">
              <div>
                <p className="eyebrow">Запрос</p>
                <h2>Вопрос</h2>
              </div>
              <button className="primary-button" type="submit" disabled={loading}>
                {loading ? "Думаю..." : "Спросить"}
              </button>
            </div>

            <label className="field">
              <span>Сообщение</span>
              <textarea value={message} onChange={(event) => setMessage(event.target.value)} />
            </label>

            <div className="example-grid">
              {EXAMPLES.map((example) => (
                <button type="button" className="example-button" key={example} onClick={() => setMessage(example)}>
                  {example}
                </button>
              ))}
            </div>

            <label className="toggle summary-toggle">
              <input checked={forceSummary} type="checkbox" onChange={(event) => setForceSummary(event.target.checked)} />
              <span>Попросить аналитический вывод</span>
            </label>

            <RequestProgress loading={loading} startedAt={startedAt} estimate={estimate} />

            {error && <div className="alert error">{error}</div>}
          </form>

          <RequestHistory
            entries={history}
            onSelect={(entry) => {
              setMessage(entry.title);
              if (entry.result) {
                setResult(entry.result);
              }
            }}
            onClear={clearHistory}
          />
        </div>

        <ResultView result={result} />
      </div>
    </main>
  );
}

function estimateChatWait(message: string, forceSummary: boolean) {
  const lowered = message.toLowerCase();
  const looksLikeRag = ["похож", "книг", "облож", "страниц", "что пишут", "примеры"].some((item) => lowered.includes(item));

  if (looksLikeRag) {
    return "обычно 20-90 сек; первый запуск BGE-M3 может занять 1-3 мин";
  }
  if (forceSummary) {
    return "обычно 10-40 сек";
  }
  return "обычно 2-10 сек";
}
