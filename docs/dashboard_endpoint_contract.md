# Контракт эндпоинта `/dashboard`

Агрегирующий эндпоинт под главный экран (дашборд). Сейчас фронт собирает обзор из
отдельных `/templates/*/execute` вызовов — это дорого и не даёт единой картины.
`/dashboard` возвращает всё, что нужно обзорному экрану, одним запросом.

Имена блоков намеренно совпадают с существующими схемами
(`app/schemas/query.py`: `MetricBlock`, `warnings`, `TraceStep`), чтобы бэкенд
переиспользовал уже написанный код и сериализацию.

---

## Запрос

```
POST /api/v1/dashboard
Content-Type: application/json
```

```jsonc
{
  "filters": {                    // тот же ReviewFilters, что и в шаблонах
    "date_from": "2025-08-04",    // null → min(review_date)
    "date_to":   "2025-10-20",    // null → max(review_date)
    "category":  null,
    "brand":     null,
    "product_id": null,
    "min_rating": null,
    "max_rating": null
  },
  "granularity": "week",          // "day" | "week" | "month"  (для series)
  "top_products_limit": 5,
  "examples_per_problem": 3       // сколько отзывов-подтверждений тянуть в growth-блок; 0 = не тянуть
}
```

Предыдущий равный период (для дельт роста) вычисляется на бэкенде: та же длина,
непосредственно перед `[date_from, date_to]`.

---

## Ответ `DashboardResponse`

```jsonc
{
  "meta": {
    "total_reviews": 48320,
    "period": { "date_from": "2025-08-04", "date_to": "2025-10-20" },
    "prev_period": { "date_from": "2025-05-28", "date_to": "2025-08-03" },
    "granularity": "week",
    "buckets": ["2025-08-04", "2025-08-11", "..."],   // подписи оси X
    "execution_ms": 54
  },

  // KPI-плашки. MetricBlock расширен полями delta/basis (обратная совместимость: они optional)
  "metrics": [
    { "name": "Всего отзывов", "value": 48320, "unit": null, "delta_pct": null, "kind": "fact" },
    { "name": "Доля негатива", "value": 41.9, "unit": "%", "delta_pct": 3.0, "delta_dir": "up_bad", "kind": "fact" },
    { "name": "Самая растущая проблема", "value": "Комплектация / упаковка",
      "unit": null, "delta_pct": 34.0, "delta_dir": "up_bad", "label_key": "pack", "kind": "fact" },
    { "name": "Период данных", "value": 12, "unit": "нед.", "kind": "fact" }
  ],

  // Топ проблем + доли + рост — единый блок (карточка «Топ проблем» и «На что смотреть» читают его же)
  "positive": { "label": "Положительный / нейтральный отзыв", "count": 28074, "share": 0.581 },
  "problems": [
    {
      "label_key": "pack",
      "label": "Проблема с комплектацией / упаковкой",
      "count": 3431,
      "share": 0.071,               // доля от всех отзывов периода
      "delta_pct": 34.0,            // рост к прошлому равному периоду
      "delta_dir": "up_bad",        // up_bad | down_good | flat
      "spark": [5.8, 6.1, 6.4, 7.0, 7.1] // доля по бакетам, для мини-графика
    }
    // ... 8 проблемных классов; порядок — по share desc (клиент сам сортирует по delta для алертов)
  ],

  // Динамика: доля каждого класса и «всего негатив» по бакетам (буквы совпадают с meta.buckets)
  "series": {
    "negative_share": [39.1, 40.2, 41.0, "..."],       // сумма проблемных долей по бакету, %
    "by_label": {
      "pack":    [5.8, 6.1, 6.4, "..."],
      "quality": [16.1, 16.4, "..."]
      // ключи = label_key всех 9 классов, значения в %
    }
  },

  // Позитив ↔ проблемы во времени (для нижней карточки)
  "positive_vs_problem": {
    "positive_share": [59.8, 58.9, "..."],  // %
    "problem_share":  [40.2, 41.1, "..."]   // % (= 100 - positive для наглядности структуры)
  },

  // Топ товаров с риск-скором
  "top_products": [
    {
      "product_id": "1240",
      "product_name": "Джинсы mom fit, синие",
      "brand": "DENIM CO",
      "total": 1240,
      "problem_share": 0.62,
      "risk_score": 78,                       // 0..100, взвешенная тяжесть проблем × объём
      "top_labels": ["size", "quality"]
    }
  ],

  // Предупреждения о данных — на языке продавца, НЕ технический текст
  "warnings": [
    { "code": "approx_dates",
      "message": "Даты у ~4% отзывов приблизительные — динамика по неделям оценочная." },
    { "code": "sparse_products",
      "message": "Товар заполнен не у всех отзывов, поэтому рейтинг товаров может быть неполным." }
  ],

  // «Как посчитано» — те же TraceStep, что и в AnswerResponse
  "trace_steps": [
    { "id": "filter",  "title": "Отобрали отзывы по фильтрам", "status": "ok", "duration_ms": 12,
      "input": { "date_from": "2025-08-04", "date_to": "2025-10-20" },
      "output": { "reviews": 48320 } },
    { "id": "labels",  "title": "Метки классификатора", "status": "ok", "duration_ms": null,
      "input": {}, "output": { "model": "bge-m3 + LinearSVC", "classes": 9 } },
    { "id": "aggregate", "title": "Свернули в доли и динамику", "status": "ok", "duration_ms": 34,
      "input": { "group_by": "week" }, "output": { "buckets": 12 } },
    { "id": "delta",   "title": "Сравнили с прошлым периодом", "status": "ok", "duration_ms": 8,
      "input": {}, "output": {} }
  ]
}
```

---

## Правила расчёта (важно для доверия)

- **Доля** класса = `count(отзывы с этой меткой) / total_reviews` за период. Из-за
  multilabel сумма долей всех классов > 100% — это нормально, каждая доля независима.
- **Доля негатива** = доля отзывов, у которых есть ≥1 проблемная метка (НЕ сумма
  долей — иначе двойной счёт multilabel). Считать отдельным `COUNT(DISTINCT review_id)`.
- **delta_pct** = `(share_now - share_prev) / share_prev * 100`, округление до целого
  для алертов. Если `share_prev == 0` → `delta_dir = "new"`, `delta_pct = null`.
- **risk_score** — прозрачная формула, раскрывается в «Как посчитано»:
  `risk = round(100 * problem_share * severity_weight)`, где severity_weight —
  фиксированные веса тяжести по классам (напр. качество/возврат тяжелее упаковки).
- Всё, что помечено `kind:"fact"` — из SQL. Объяснения ИИ (гипотезы) сюда НЕ входят:
  они приходят только в чат/drill-down с обязательными `review_id`-подтверждениями.

## Замечания по реализации

- Один SQL-проход по `reviews ⋈ review_labels` с `FILTER (WHERE ...)` агрегатами
  закрывает `positive`, `problems`, `series` — не нужно 9 отдельных запросов.
- `date_bucket` через `date_trunc(granularity, review_date)`; пустые бакеты
  заполнять нулями на бэкенде, чтобы ось X была ровной.
- Кэш на `(filters, granularity)` на 1–5 мин — обзор не требует секундной свежести.
- Пустой результат (0 отзывов) → `metrics` с `value:null`, пустые `problems/series`,
  и `warnings` с подсказкой расширить период. Фронт показывает empty-state.
```
