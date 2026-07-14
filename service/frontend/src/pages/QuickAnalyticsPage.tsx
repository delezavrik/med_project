import { useEffect, useState } from "react";
import { getFacets, getTemplates } from "../api/client";
import type { AnswerResponse, FacetsResponse, TemplateInfo } from "../api/types";
import { QuickAnalyticsForm } from "../components/QuickAnalyticsForm";
import {
  createHistoryEntry,
  loadHistory,
  RequestHistory,
  saveHistory,
  type HistoryEntry,
} from "../components/RequestHistory";
import { ResultView } from "../components/ResultView";

export function QuickAnalyticsPage() {
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [loadWarning, setLoadWarning] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>(() => loadHistory());

  useEffect(() => {
    async function loadMetadata() {
      try {
        const [templatesResponse, facetsResponse] = await Promise.all([getTemplates(), getFacets()]);
        setTemplates(templatesResponse);
        setFacets(facetsResponse);
        setLoadWarning(facetsResponse.warnings.join(" ") || null);
      } catch (caught) {
        setLoadWarning(caught instanceof Error ? caught.message : String(caught));
      }
    }

    void loadMetadata();
  }, []);

  function handleResult(response: AnswerResponse) {
    setResult(response);
    const templateTitle = templates.find((template) => template.id === response.parsed_query.intent)?.title;
    const fallbackTitle = response.parsed_query.intent;
    addHistoryEntry(createHistoryEntry("template", templateTitle || fallbackTitle, response));
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

  return (
    <main className="workspace">
      <section className="intro">
        <p className="eyebrow">MVP аналитики отзывов</p>
        <h1>Быстрая проверка сценариев</h1>
        <p>
          Выбери сценарий, задай фильтры и посмотри расчет по PostgreSQL. Поля формы меняются под выбранный сценарий.
        </p>
        {loadWarning && <div className="alert warning">{loadWarning}</div>}
      </section>

      <div className="layout">
        <div className="stack">
          <QuickAnalyticsForm templates={templates} facets={facets} onResult={handleResult} />
          <RequestHistory
            entries={history}
            onSelect={(entry) => {
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
