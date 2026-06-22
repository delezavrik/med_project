# Локальная PostgreSQL + Qdrant база для проекта отзывов WB

Эта папка поднимает локально две долгоживущие базы:

- **PostgreSQL** — отзывы, метаданные, предсказанные классы.
- **Qdrant** — embeddings отзывов для RAG / semantic search.

Данные хранятся в папке `storage/`, поэтому не пропадают после перезапуска контейнеров.

---

## 1. Рекомендуемая структура проекта

Положи эти файлы в корень проекта так:

```text
med_project/
├── docker-compose.yml
├── .env
├── requirements.txt
├── infra/
│   └── postgres/
│       └── init/
│           └── 001_schema.sql
├── scripts/
│   ├── load_postgres.py
│   ├── load_qdrant.py
│   ├── check_postgres.py
│   ├── check_qdrant.py
│   └── rag_smoke_test.py
├── data/
│   └── db_exports/
│       ├── postgres_reviews_bge_m3_linearsvc_saved_model/
│       │   ├── reviews_for_postgres.parquet
│       │   ├── reviews_for_postgres.csv
│       │   ├── predicted_label_stats.csv
│       │   └── postgres_export_manifest.json
│       └── qdrant_vectors_baai_bge_m3/
│           ├── qdrant_vectors.npy
│           ├── qdrant_payload.parquet
│           ├── qdrant_payload.csv
│           └── qdrant_manifest.json
└── storage/
    ├── postgres_data/
    └── qdrant_storage/
```

`storage/` создастся автоматически после запуска Docker Compose.

---

## 2. Куда распаковать два скачанных архива

Первый архив, который относится к PostgreSQL, распакуй сюда:

```text
data/db_exports/postgres_reviews_bge_m3_linearsvc_saved_model/
```

Внутри обязательно должен быть файл:

```text
data/db_exports/postgres_reviews_bge_m3_linearsvc_saved_model/reviews_for_postgres.parquet
```

Второй архив, который относится к Qdrant, распакуй сюда:

```text
data/db_exports/qdrant_vectors_baai_bge_m3/
```

Внутри обязательно должны быть файлы:

```text
data/db_exports/qdrant_vectors_baai_bge_m3/qdrant_vectors.npy
data/db_exports/qdrant_vectors_baai_bge_m3/qdrant_payload.parquet
```

Если у тебя папка Qdrant называется иначе, поменяй путь в `.env`.

---

## 3. Первый запуск

Создай `.env`:

```bash
cp .env.example .env
```

Запусти базы:

```bash
docker compose up -d
```

Проверь контейнеры:

```bash
docker ps
```

Должны быть:

```text
wb_reviews_postgres
wb_reviews_qdrant
```

---

## 4. Установить Python-зависимости локально

Лучше в виртуальном окружении:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 5. Загрузить данные в PostgreSQL

```bash
python scripts/load_postgres.py
```

Проверить:

```bash
python scripts/check_postgres.py
```

---

## 6. Загрузить данные в Qdrant

```bash
python scripts/load_qdrant.py
```

Проверить:

```bash
python scripts/check_qdrant.py
```

---

## 7. Быстрая проверка RAG-поиска

```bash
python scripts/rag_smoke_test.py
```

Можно задать свой запрос:

```bash
RAG_QUERY="книга пришла с рваной обложкой" python scripts/rag_smoke_test.py
```

Схема работы:

```text
запрос пользователя
→ embedding той же моделью, что использовалась для Qdrant
→ поиск похожих review_id в Qdrant
→ получение полных текстов из PostgreSQL
```

---

## 8. Важные команды Docker

Остановить контейнеры, но оставить данные:

```bash
docker compose down
```

Запустить снова:

```bash
docker compose up -d
```

Удалить контейнеры и данные:

```bash
docker compose down
rm -rf storage/postgres_data storage/qdrant_storage
```

Осторожно: это удалит локальную БД.

---

## 9. Бэкап

PostgreSQL dump:

```bash
mkdir -p backups

docker exec wb_reviews_postgres pg_dump -U reviews_user -d reviews_db > backups/reviews_db_$(date +%Y%m%d_%H%M%S).sql
```

Qdrant проще бэкапить копированием папки:

```bash
mkdir -p backups
cp -R storage/qdrant_storage backups/qdrant_storage_$(date +%Y%m%d_%H%M%S)
```

Для MVP этого достаточно.

---

## 10. Если хочешь перезагрузить данные заново

Для PostgreSQL можно очистить таблицу перед загрузкой:

```bash
TRUNCATE_BEFORE_LOAD=1 python scripts/load_postgres.py
```

Для Qdrant можно пересоздать collection:

```bash
RECREATE_QDRANT_COLLECTION=1 python scripts/load_qdrant.py
```
