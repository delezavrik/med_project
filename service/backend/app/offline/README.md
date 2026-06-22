# Offline pipeline

Эта папка нужна для будущего переноса ноутбуков в регулярные скрипты/джобы.

Идеальная схема:

```text
1. ingest_reviews.py       # загрузить новые отзывы
2. normalize_reviews.py    # очистить текст и привести колонки
3. classify_reviews.py     # поставить labels классификатором
4. load_postgres.py        # сохранить отзывы и labels в PostgreSQL
5. build_embeddings.py     # построить эмбеддинги
6. load_qdrant.py          # сохранить векторы и payload в Qdrant
```

Пока ноутбуки в `dataset/` и `algs/` остаются источником экспериментов.
Когда модель и формат данных стабилизируются, логику можно переносить сюда.
