import { useState } from "react";
import { executeTemplate } from "../api/client";
import type { AnswerResponse, TemplateExecuteRequest } from "../api/types";
import { PROBLEM_LABELS, QUICK_ANALYTICS_TEMPLATES } from "../config/templates";

interface Props {
  onResult: (result: AnswerResponse) => void;
}

export function QuickAnalyticsForm({ onResult }: Props) {
  const [templateId, setTemplateId] = useState("count_by_problem");
  const [label, setLabel] = useState("Доставка/получение");
  const [category, setCategory] = useState("Книги");
  const [dateFrom, setDateFrom] = useState("2025-08-01");
  const [dateTo, setDateTo] = useState("2025-10-15");
  const [addSummary, setAddSummary] = useState(false);
  const [loading, setLoading] = useState(false);

  const selectedTemplate = QUICK_ANALYTICS_TEMPLATES.find((template) => template.id === templateId);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);

    const request: TemplateExecuteRequest = {
      filters: {
        date_from: dateFrom || null,
        date_to: dateTo || null,
        labels: label ? [label] : [],
        category: category || null,
      },
      add_analytical_summary: addSummary,
      limit: 20,
    };

    try {
      const result = await executeTemplate(templateId, request);
      onResult(result);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Сценарий
        <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
          {QUICK_ANALYTICS_TEMPLATES.map((template) => (
            <option key={template.id} value={template.id}>{template.title}</option>
          ))}
        </select>
      </label>

      <label>
        Период c
        <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
      </label>

      <label>
        по
        <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
      </label>

      <label>
        Класс проблемы
        <select value={label} onChange={(event) => setLabel(event.target.value)}>
          {PROBLEM_LABELS.map((item) => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
      </label>

      <label>
        Категория
        <input value={category} onChange={(event) => setCategory(event.target.value)} />
      </label>

      {selectedTemplate?.showAnalyticalSummaryToggle && (
        <label>
          <input
            type="checkbox"
            checked={addSummary}
            onChange={(event) => setAddSummary(event.target.checked)}
          />
          Добавить аналитический вывод
        </label>
      )}

      <button type="submit" disabled={loading}>{loading ? "Считаю..." : "Показать"}</button>
    </form>
  );
}
