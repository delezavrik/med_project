import type { AnswerResponse } from "../api/types";
import { formatDuration } from "./RequestProgress";

export interface HistoryEntry {
  id: string;
  kind: "chat" | "template";
  title: string;
  answer: string;
  intent: string;
  createdAt: string;
  executionMs?: number | null;
  result?: AnswerResponse;
}

interface Props {
  entries: HistoryEntry[];
  onSelect: (entry: HistoryEntry) => void;
  onClear: () => void;
}

export const HISTORY_STORAGE_KEY = "reviews_analytics_request_history";

export function createHistoryEntry(kind: HistoryEntry["kind"], title: string, result: AnswerResponse): HistoryEntry {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    kind,
    title,
    answer: result.answer_text,
    intent: result.parsed_query.intent,
    createdAt: new Date().toISOString(),
    executionMs: result.execution_ms,
    result,
  };
}

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = window.localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveHistory(entries: HistoryEntry[]) {
  window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(entries.slice(0, 30)));
}

export function RequestHistory({ entries, onSelect, onClear }: Props) {
  return (
    <section className="panel history-panel">
      <div className="history-header">
        <div>
          <p className="eyebrow">История</p>
          <h2>Последние запросы</h2>
        </div>
        <button className="ghost-button" type="button" onClick={onClear} disabled={entries.length === 0}>
          Очистить
        </button>
      </div>

      {entries.length === 0 ? (
        <p className="muted">История появится после первого запроса.</p>
      ) : (
        <div className="history-list">
          {entries.map((entry) => (
            <button className="history-item" type="button" key={entry.id} onClick={() => onSelect(entry)}>
              <strong>{entry.title}</strong>
              <span>{entry.answer}</span>
              <small>
                {formatDate(entry.createdAt)} · {entry.intent}
                {entry.executionMs ? ` · ${formatDuration(entry.executionMs)}` : ""}
              </small>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
