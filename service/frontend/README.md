# Frontend integration layer

Это не полноценный React-проект, а заготовки, которые можно перенести в сайт.

Что здесь есть:

```text
src/api/types.ts              # типы ParsedQuery / AnswerResponse
src/api/client.ts             # функции вызова backend
src/config/templates.ts       # конфиг шаблонов для UI
src/components/QuickAnalyticsForm.tsx
src/pages/QuickAnalyticsPage.tsx
src/pages/ChatAnalyticsPage.tsx
```

Идея для сайта:

```text
/analytics/quick   # шаблонная аналитика
/analytics/chat    # чат с LLM
```

Обе страницы отправляют запросы в один backend и получают единый `AnswerResponse`.
