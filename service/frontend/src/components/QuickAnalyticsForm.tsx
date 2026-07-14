import { useEffect, useMemo, useState, type FormEvent } from "react";
import { executeTemplate } from "../api/client";
import type { AnswerResponse, FacetsResponse, GroupBy, TemplateExecuteRequest, TemplateInfo } from "../api/types";
import { GROUP_BY_OPTIONS, PROBLEM_LABELS, QUICK_ANALYTICS_TEMPLATES } from "../config/templates";
import { RequestProgress } from "./RequestProgress";

interface Props {
  templates?: TemplateInfo[];
  facets?: FacetsResponse | null;
  onResult: (result: AnswerResponse) => void;
}

const DEFAULT_DATE_FROM = "2025-08-01";
const DEFAULT_DATE_TO = "2025-10-15";
const CUSTOM_CATEGORY_VALUE = "__custom_category__";

function mergeTemplates(templates?: TemplateInfo[]): TemplateInfo[] {
  if (!templates?.length) {
    return QUICK_ANALYTICS_TEMPLATES;
  }

  return QUICK_ANALYTICS_TEMPLATES.map((localTemplate) => {
    const apiTemplate = templates.find((template) => template.id === localTemplate.id);
    return apiTemplate ? { ...localTemplate, ...apiTemplate } : localTemplate;
  });
}

export function QuickAnalyticsForm({ templates, facets, onResult }: Props) {
  const availableTemplates = useMemo(() => mergeTemplates(templates), [templates]);
  const labels = facets?.labels?.length ? facets.labels : PROBLEM_LABELS;
  const problemLabels = facets?.problem_labels?.length ? facets.problem_labels : labels;

  const [templateId, setTemplateId] = useState("top_problems");
  const [selectedLabels, setSelectedLabels] = useState<string[]>([]);
  const [useLabelSubset, setUseLabelSubset] = useState(false);
  const [categoryPreset, setCategoryPreset] = useState("");
  const [customCategory, setCustomCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [productName, setProductName] = useState("");
  const [dateFrom, setDateFrom] = useState(facets?.date_min || "");
  const [dateTo, setDateTo] = useState(facets?.date_max || "");
  const [keyword, setKeyword] = useState("");
  const [groupBy, setGroupBy] = useState<GroupBy | "">("");
  const [minRating, setMinRating] = useState("");
  const [maxRating, setMaxRating] = useState("");
  const [limit, setLimit] = useState(20);
  const [examplesLimit, setExamplesLimit] = useState(5);
  const [addSummary, setAddSummary] = useState(false);
  const [loading, setLoading] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedTemplate = availableTemplates.find((template) => template.id === templateId) || availableTemplates[0];
  const labelMode = selectedTemplate.label_mode;
  const keywordMode = selectedTemplate.keyword_mode;
  const shouldShowLabels = labelMode !== "hidden";
  const shouldSendLabels = labelMode === "required" || useLabelSubset;
  const shouldShowKeyword = keywordMode !== "hidden";
  const shouldShowGroupBy = ["problem_dynamics", "positive_vs_problem"].includes(selectedTemplate.id);
  const shouldShowExamplesLimit = selectedTemplate.id === "top_problems";
  const labelOptions = labelMode === "required" || labelMode === "subset" ? problemLabels : labels;
  const categoryProblemLabel = categoryPreset && categoryPreset !== CUSTOM_CATEGORY_VALUE ? categoryPreset : null;
  const categoryForRequest = categoryPreset === CUSTOM_CATEGORY_VALUE ? customCategory.trim() : "";
  const hasDateFacets = Boolean(facets?.date_min && facets?.date_max);

  useEffect(() => {
    setDateFrom(facets?.date_min || "");
    setDateTo(facets?.date_max || "");
  }, [facets?.date_min, facets?.date_max]);

  function toggleLabel(label: string) {
    setSelectedLabels((current) => (
      current.includes(label)
        ? current.filter((item) => item !== label)
        : [...current, label]
    ));
  }

  function selectAllProblems() {
    setSelectedLabels(problemLabels.filter((label) => label !== facets?.positive_label));
    setUseLabelSubset(true);
  }

  function clearLabels() {
    setSelectedLabels([]);
  }

  function buildRequest(): TemplateExecuteRequest {
    const labelsForRequest = Array.from(new Set([
      ...(shouldSendLabels ? selectedLabels : []),
      ...(categoryProblemLabel ? [categoryProblemLabel] : []),
    ]));

    return {
      filters: {
        date_from: dateFrom || null,
        date_to: dateTo || null,
        labels: labelsForRequest,
        keyword: shouldShowKeyword && keyword.trim() ? keyword.trim() : null,
        category: categoryForRequest || null,
        brand: brand.trim() || null,
        product_name: productName.trim() || null,
        min_rating: minRating ? Number(minRating) : null,
        max_rating: maxRating ? Number(maxRating) : null,
      },
      group_by: shouldShowGroupBy && groupBy ? groupBy : null,
      semantic_query: selectedTemplate.needs_semantic_query && keyword.trim() ? keyword.trim() : null,
      add_analytical_summary: addSummary,
      limit,
      examples_limit: shouldShowExamplesLimit ? examplesLimit : 0,
    };
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (labelMode === "required" && selectedLabels.length === 0 && !categoryProblemLabel) {
      setError("Для этого сценария выбери хотя бы одну проблему.");
      return;
    }

    if (keywordMode === "required" && !keyword.trim()) {
      setError("Для поиска по слову нужна фраза или ключевое слово.");
      return;
    }

    setLoading(true);
    setStartedAt(Date.now());
    try {
      const result = await executeTemplate(templateId, buildRequest());
      onResult(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="panel form-panel" onSubmit={handleSubmit}>
      <div className="panel-header">
        <div>
          <p className="eyebrow">Шаблонная аналитика</p>
          <h2>Проверка сценария</h2>
        </div>
        <button className="primary-button" type="submit" disabled={loading}>
          {loading ? "Считаю..." : "Запустить"}
        </button>
      </div>

      <label className="field">
        <span>Сценарий</span>
        <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
          {availableTemplates.map((template) => (
            <option key={template.id} value={template.id}>{template.title}</option>
          ))}
        </select>
      </label>

      <p className="muted">{selectedTemplate.description}</p>

      <div className="grid two">
        <label className="field">
          <span>Период c</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            placeholder={DEFAULT_DATE_FROM}
            disabled={!hasDateFacets}
          />
        </label>
        <label className="field">
          <span>по</span>
          <input
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            placeholder={DEFAULT_DATE_TO}
            disabled={!hasDateFacets}
          />
        </label>
      </div>
      {!hasDateFacets && (
        <p className="muted">
          В загруженных данных нет даты отзыва, поэтому период по умолчанию не применяется.
        </p>
      )}

      <div className="grid three">
        <label className="field">
          <span>Категория</span>
          <select value={categoryPreset} onChange={(event) => setCategoryPreset(event.target.value)}>
            <option value="">Любая</option>
            {problemLabels.map((item) => <option key={item} value={item}>{formatProblemOption(item)}</option>)}
            <option value={CUSTOM_CATEGORY_VALUE}>Своя категория</option>
          </select>
        </label>
        <label className="field">
          <span>Бренд</span>
          <input list="brands" value={brand} onChange={(event) => setBrand(event.target.value)} placeholder="Любой" />
        </label>
        <label className="field">
          <span>Товар</span>
          <input list="products" value={productName} onChange={(event) => setProductName(event.target.value)} placeholder="Любой" />
        </label>
      </div>

      {categoryPreset === CUSTOM_CATEGORY_VALUE && (
        <label className="field">
          <span>Своя товарная категория</span>
          <input
            list="categories"
            value={customCategory}
            onChange={(event) => setCustomCategory(event.target.value)}
            placeholder="Например: Книги"
          />
        </label>
      )}

      <datalist id="categories">
        {facets?.categories.map((item) => <option key={item} value={item} />)}
      </datalist>
      <datalist id="brands">
        {facets?.brands.map((item) => <option key={item} value={item} />)}
      </datalist>
      <datalist id="products">
        {facets?.products.map((item) => (
          <option key={`${item.product_id}-${item.product_name}`} value={item.product_name || item.product_id || ""} />
        ))}
      </datalist>

      {shouldShowLabels && (
        <section className="filter-box">
          <div className="filter-box-header">
            <div>
              <strong>Проблемы</strong>
              <p>
                {labelMode === "required"
                  ? "Выбор обязателен для этого сценария."
                  : "По умолчанию сценарий считает по всем проблемам."}
              </p>
            </div>
            {labelMode !== "required" && (
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={useLabelSubset}
                  onChange={(event) => setUseLabelSubset(event.target.checked)}
                />
                <span>Ограничить проблемами</span>
              </label>
            )}
          </div>

          {(labelMode === "required" || useLabelSubset) && (
            <>
              <div className="label-grid">
                {labelOptions.map((item) => (
                  <label className="check-card" key={item}>
                    <input
                      type="checkbox"
                      checked={selectedLabels.includes(item)}
                      onChange={() => toggleLabel(item)}
                    />
                    <span>{item}</span>
                  </label>
                ))}
              </div>
              <div className="inline-actions">
                <button type="button" className="ghost-button" onClick={selectAllProblems}>Все проблемы</button>
                <button type="button" className="ghost-button" onClick={clearLabels}>Очистить</button>
              </div>
            </>
          )}
        </section>
      )}

      {shouldShowKeyword && (
        <label className="field">
          <span>
            {selectedTemplate.needs_semantic_query
              ? "Смысловой запрос для RAG"
              : keywordMode === "required" ? "Ключевое слово или фраза" : "Ключевое слово"}
          </span>
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="например: рваные обложки у книг" />
        </label>
      )}

      <div className="grid three">
        {shouldShowGroupBy && (
          <label className="field">
            <span>Группировка</span>
            <select value={groupBy} onChange={(event) => setGroupBy(event.target.value as GroupBy | "")}>
              <option value="">По умолчанию</option>
              {GROUP_BY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
        )}
        <label className="field">
          <span>Рейтинг от</span>
          <select value={minRating} onChange={(event) => setMinRating(event.target.value)}>
            <option value="">Любой</option>
            {[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Рейтинг до</span>
          <select value={maxRating} onChange={(event) => setMaxRating(event.target.value)}>
            <option value="">Любой</option>
            {[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Строк</span>
          <input
            type="number"
            min={1}
            max={200}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          />
        </label>
        {shouldShowExamplesLimit && (
          <label className="field">
            <span>Примеров отзывов</span>
            <input
              type="number"
              min={0}
              max={20}
              value={examplesLimit}
              onChange={(event) => setExamplesLimit(clampNumber(Number(event.target.value), 0, 20))}
            />
          </label>
        )}
      </div>

      {selectedTemplate.allow_llm_summary && (
        <label className="toggle summary-toggle">
          <input checked={addSummary} type="checkbox" onChange={(event) => setAddSummary(event.target.checked)} />
          <span>Добавить аналитический вывод</span>
        </label>
      )}

      <RequestProgress loading={loading} startedAt={startedAt} estimate={estimateTemplateWait(selectedTemplate, addSummary)} />

      {error && <div className="alert error">{error}</div>}
    </form>
  );
}

function estimateTemplateWait(template: TemplateInfo, addSummary: boolean) {
  if (template.needs_semantic_query) {
    return "обычно 20-90 сек; первый запуск BGE-M3 может занять 1-3 мин";
  }
  if (addSummary || template.default_answer_mode === "llm") {
    return "обычно 10-40 сек";
  }
  return "обычно 1-8 сек";
}

function clampNumber(value: number, min: number, max: number) {
  if (Number.isNaN(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, value));
}

function formatProblemOption(label: string) {
  if (label === "Проблема с качеством товара") {
    return `${label} (брак / дефект)`;
  }
  if (label === "Проблема с комплектацией / упаковкой") {
    return `${label} (упаковка / комплект)`;
  }
  return label;
}
