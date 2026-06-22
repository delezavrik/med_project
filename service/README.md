# service — MVP-приложение для анализа отзывов

Эта папка лежит внутри `med_project/` и отвечает за продуктовый слой:

```text
med_project/
├── dataset/      # ноутбуки и данные
├── algs/         # эксперименты с моделями
├── docs/         # документация
└── service/      # backend/frontend приложения
```

Текущий MVP-срез:

```text
CSV с размеченными отзывами
    ↓
PostgreSQL
    ↓
FastAPI backend
    ↓
шаблонная аналитика с реальными числами
```

Qdrant, online ingestion и полноценный frontend пока оставлены как следующий этап.

---

## 1. Запуск через Docker Compose

Из папки проекта:

```bash
cd ~/Documents/med_project/service
cp backend/.env.docker.example backend/.env
docker compose -f docker-compose.dev.yml up --build
```

Backend будет здесь:

```text
http://localhost:8000
http://localhost:8000/docs
```

Проверка:

```bash
curl http://localhost:8000/health
```

PostgreSQL проброшен наружу на порт `5433`, потому что `5432` часто уже занят старым Postgres:

```text
localhost:5433 -> postgres:5432 внутри Docker
```

---

## 2. Создать demo CSV

В другом терминале:

```bash
cd ~/Documents/med_project/service/backend
```

Если зависимости еще не стоят локально:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Если используешь общий venv из `med_project/.venv`, активируй его вместо этого.

Создать demo CSV:

```bash
python -m app.offline.make_demo_reviews_csv --output /tmp/demo_reviews.csv
```

---

## 3. Загрузить demo CSV в PostgreSQL

```bash
python -m app.offline.import_reviews_to_postgres \
  --input /tmp/demo_reviews.csv \
  --dsn postgresql://reviews_user:reviews_password@localhost:5433/reviews_db \
  --init-schema
```

Проверить, что данные появились:

```bash
curl http://localhost:8000/api/v1/debug/db-stats
```

Ожидаемо: `reviews_count` должен быть больше нуля.

---

## 4. Проверить аналитику

Количество отзывов с проблемой `Упаковка` в категории `Книги`:

```bash
curl -X POST "http://localhost:8000/api/v1/templates/count_by_problem/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": {
      "labels": ["Упаковка"],
      "category": "Книги"
    },
    "add_analytical_summary": false,
    "limit": 20
  }'
```

Топ проблем:

```bash
curl -X POST "http://localhost:8000/api/v1/templates/top_problems/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": {
      "category": "Книги"
    },
    "add_analytical_summary": false,
    "limit": 20
  }'
```

---

## 5. Загрузить свой размеченный CSV

Пример для файла с колонками `отзыв` и `labels`:

```bash
cd ~/Documents/med_project/service/backend

python -m app.offline.import_reviews_to_postgres \
  --input ../../labeled/wb_feedbacks_ChatGpt_markup_from_synthetic_gpt5_V_2/chatgpt_labeled_reviews_mvp_combined.csv \
  --dsn postgresql://reviews_user:reviews_password@localhost:5433/reviews_db \
  --init-schema \
  --default-date 2025-01-01 \
  --default-category "Тестовая категория" \
  --model-name "gpt5_imported_labels"
```

Если колонки называются иначе:

```bash
python -m app.offline.import_reviews_to_postgres \
  --input /path/to/file.csv \
  --dsn postgresql://reviews_user:reviews_password@localhost:5433/reviews_db \
  --text-column "отзыв" \
  --labels-column "labels" \
  --default-date 2025-01-01
```

---

## Что сейчас работает

```text
GET  /health
GET  /api/v1/templates
GET  /api/v1/debug/db-stats
POST /api/v1/templates/{template_id}/execute
POST /api/v1/query/execute
POST /api/v1/chat/ask
```

Сейчас реально рабочие PostgreSQL-сценарии:

```text
count_by_problem
 top_problems
problem_dynamics
top_products_by_problem
```

Qdrant-сценарии пока вернут warning, потому что embedding-модель еще не подключена.
