## Описание файлов папки `clustering`

### `make_shuffle_samples_190_000_for_HDBSCAN.ipynb`

Формирует исходную raw-выборку отзывов для дальнейшей кластеризации через HDBSCAN.

Ноутбук читает parquet-файлы из директории с полными отзывами, случайно берет ограниченное число строк из каждого файла и сохраняет результат в отдельную папку с sample-файлами. Каждые 1000 отзывов сохраняются в отдельный `sample_part_*.parquet`, чтобы данные было удобнее обрабатывать дальше.

Основной результат:

* `data/hdbscan_raw_sample_200_files_1000_each/sample_part_*.parquet`
* `sample_manifest.csv`
* `sample_meta.json`

---

### `HDBSCAN.ipynb`

Запускает основной пайплайн кластеризации отзывов.

Ноутбук берет подготовленные sample-файлы, очищает текстовую колонку, строит эмбеддинги отзывов с помощью `SentenceTransformer`, снижает размерность через UMAP и затем применяет HDBSCAN для поиска смысловых кластеров отзывов.

Основной результат:

* `hdbscan_clusters.parquet`
* `hdbscan_clusters.csv`
* `cluster_summary.csv`
* `embeddings_full_normalized.npy`
* `umap_features.npy`
* `hdbscan_param_search.csv`

Файл нужен для того, чтобы найти группы похожих отзывов и дальше использовать эти группы для анализа и добора размеченных примеров.

---

### `analyzes_the_clusters_obtained_by_the_HDBSCAN.ipynb`

Анализирует уже полученные HDBSCAN-кластеры с помощью LLM.

Ноутбук не пересчитывает кластеризацию и не размечает каждый отзыв отдельно. Он берет файл `hdbscan_clusters.parquet`, выбирает несколько характерных отзывов из каждого кластера и отправляет их в LLM, чтобы получить краткое описание кластера: название, основную тему, подходящие классы и примеры признаков.

Основной результат:

* `cluster_llm_analysis.csv`
* `cluster_llm_analysis.parquet`
* `cluster_llm_analysis.jsonl`
* `hdbscan_clusters_with_llm_analysis.parquet`
* `hdbscan_clusters_with_llm_analysis.csv`

Файл нужен для того, чтобы понять, какие кластеры содержат полезные проблемные отзывы и какие классы разметки могут в них встречаться.

---

### `extra_markup_from_hdbscan_clusters.ipynb`

Добирает дополнительные размеченные отзывы из кластеров HDBSCAN.

Ноутбук использует результаты кластеризации и LLM-анализа кластеров. Сначала выбираются кластеры, которые потенциально содержат нужные классы, затем отзывы из этих кластеров по одному отправляются в LLM для полноценной multi-label разметки.

Описание кластера используется только как фильтр для отбора кандидатов. Финальная разметка каждого отзыва выполняется отдельно через LLM.

Основной результат:

* `extra_from_hdbscan_candidate_clusters.csv`
* `extra_from_hdbscan_candidate_clusters.parquet`
* `extra_from_hdbscan_candidate_clusters_final.csv`
* `extra_from_hdbscan_candidate_clusters_class_status.csv`

Файл нужен для расширения обучающего датасета за счет отзывов из тематически подходящих кластеров.

---

### `extra_markup_from_embedding_similarity_rare_classes.ipynb`

Добирает примеры для редких классов через поиск по эмбеддингам.

Ноутбук используется после первичного добора из кластеров, когда некоторые классы все еще представлены хуже остальных. Он берет уже размеченные данные, определяет редкие классы, строит для них эмбеддинг-прототипы и ищет похожие отзывы среди кандидатов из HDBSCAN-кластеров.

После поиска похожих отзывов каждый кандидат снова проверяется через LLM. Сохраняются только те отзывы, где LLM подтвердила хотя бы один целевой редкий класс.

Основной результат:

* `extra_from_embedding_similarity_rare_classes.csv`
* `extra_from_embedding_similarity_rare_classes.parquet`
* `extra_from_embedding_similarity_rare_classes_final.csv`
* `extra_from_embedding_similarity_rare_classes_class_status.csv`
* файлы кэша эмбеддингов и прототипов классов

Файл нужен для точечного усиления слабых классов, которые плохо набираются обычным случайным отбором или простым проходом по кластерам.

---

### `train_rubert_head_only_multilabel.ipynb`

Обучает baseline-модель для multi-label классификации отзывов.

Файл напрямую не выполняет кластеризацию, но использует данные, которые были получены в том числе через кластерный добор. Ноутбук обучает модель вида:

```text
RuBERT / BERT-like encoder + замороженный encoder + Dropout + Linear layer
```

То есть веса RuBERT не дообучаются, обучается только классификационная голова сверху. Модель решает задачу multi-label классификации на 13 классов, где один отзыв может относиться сразу к нескольким классам.

Данные для обучения берутся из папок:

* `wb_feedbacks_llm_labeled_from_clusters`
* `wb_feedbacks_llm_labeled_from_sample`

Валидация дополнительно проводится на golden set.

Основной результат:

* `rubert_head_only_multilabel.pt`
* `label_mapping.json`
* `thresholds.json`
* `training_history.csv`
* `validation_metrics_tuned.csv`
* `validation_per_class_metrics.csv`
* `golden_metrics_summary.csv`
* `golden_predictions.csv`

Файл нужен для проверки, насколько собранная разметка подходит для обучения собственного классификатора отзывов.
