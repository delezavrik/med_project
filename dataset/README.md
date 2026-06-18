# Dataset pipeline

Папка содержит ноутбуки, которые последовательно формируют датасет отзывов Wildberries: от скачивания исходных parquet-файлов до GPT-5-разметки, подготовки train set и manual-check/golden set для оценки модели.

## Общая логика пайплайна

```text
nyuuzyou/wb-feedbacks
        ↓
dataset_downloading.ipynb
        ↓
data/interim/wb_feedbacks_clean_full/
        ↓
makes_200_000_random_samples_from_100_chunks.ipynb
        ↓
data/processed/random_100_chunks_2000_examples_seed_42/
        ↓
data_markup.ipynb
        ↓
data/labeled/wb_feedbacks_llm_labeled_from_sample/
        ↓
generate_by_class_with_synthetic.ipynb
        ↓
data/labeled/wb_feedbacks_by_class_with_synthetic/
        ↓
ChatGpt_markup_gpt5_from_synthetic.ipynb
        ↓
data/labeled/wb_feedbacks_ChatGpt_markup_from_synthetic_gpt5_V_2/
        ↓
train set для обучения классификатора
```

Отдельная ветка используется для ручной проверки:

```text
GPT-5-размеченные данные
        ↓
generate_manual_check_random_by_class.ipynb
        ↓
data/labeled/wb_feedbacks_manual_check_random/
        ↓
ручная проверка correct_labels
        ↓
ChatGpt_markup_gpt5_manual_check_only.ipynb
        ↓
data/labeled/wb_feedbacks_manual_check_random_gpt5_prompt_test_v5/
        ↓
golden set для оценки качества
```

## Файлы

### `dataset_downloading.ipynb`

Скачивает исходный датасет отзывов `nyuuzyou/wb-feedbacks` и сохраняет его в Google Drive.

Сохраняет две версии данных:

```text
data/raw/wb_feedbacks_full/
```

— сырые parquet-файлы.

```text
data/interim/wb_feedbacks_clean_full/
```

— минимально очищенные parquet-файлы.

Очистка здесь техническая: обрабатывается колонка `text`, убираются переносы строк, табы, лишние пробелы, пустые тексты; слишком длинные отзывы обрезаются до 5000 символов. Смысл текста не меняется.

---

### `makes_200_000_random_samples_from_100_chunks.ipynb`

Формирует большую случайную выборку из очищенных parquet-файлов.

На вход использует:

```text
data/interim/wb_feedbacks_clean_full/clean_part_*.parquet
```

Логика:

```text
100 случайных parquet-чанков × до 2000 отзывов из каждого чанка
```

На выходе сохраняет примерно 200 000 отзывов:

```text
data/processed/random_100_chunks_2000_examples_seed_42/
sample_100_chunks_2000_each.parquet
```

Эта выборка используется дальше для первичной LLM-разметки.

---

### `data_markup.ipynb`

Выполняет первичную автоматическую разметку отзывов из большой случайной выборки.

На вход использует:

```text
data/processed/random_100_chunks_2000_examples_seed_42/
sample_100_chunks_2000_each.parquet
```

Для разметки используется модель:

```text
qwen/qwen3-32b
```

Модель вызывается через Groq API. Цель этапа — не обучить классификатор, а получить первичный размеченный набор отзывов по проблемным классам.

Основной выход:

```text
data/labeled/wb_feedbacks_llm_labeled_from_sample/
balanced_50_per_class_random_chunks_final.csv
```

---

### `generate_by_class_with_synthetic.ipynb`

Собирает датасет по классам и дополняет редкие классы синтетическими отзывами.

На вход использует размеченные отзывы из папки:

```text
data/labeled/wb_feedbacks_ChatGpt_markup/
```

Если основной train-файл не найден, ноутбук использует fallback-файлы с ChatGPT-разметкой из той же папки.

Для генерации синтетики используется модель:

```text
gpt-4.1
```

Модель вызывается через OpenAI API. Синтетика нужна для выравнивания классов, где реальных примеров оказалось мало.

Выход:

```text
data/labeled/wb_feedbacks_by_class_with_synthetic/
```

Внутри сохраняются CSV-файлы по каждому классу и сводка:

```text
_summary_by_class.csv
```

---

### `ChatGpt_markup_gpt5_from_synthetic.ipynb`

Повторно размечает всю корзинку `real + synthetic` через GPT-5.

На вход использует:

```text
data/labeled/wb_feedbacks_by_class_with_synthetic/
```

Для разметки используется:

```text
gpt-5
```

Цель этапа — получить более качественную и единообразную multi-label разметку для обучения классификатора.

Основные выходы:

```text
data/labeled/wb_feedbacks_ChatGpt_markup_from_synthetic_gpt5_V_2/
chatgpt_labeled_reviews_mvp_combined.csv
chatgpt_labeled_reviews_mvp_for_training.csv
chatgpt_labeled_reviews_mvp_needs_review.csv
```

Также дополнительно сохраняются данные, заново разложенные по классам:

```text
data/labeled/wb_feedbacks_by_class_with_synthetic_gpt5_relabelled_V_2/
```

Файл `chatgpt_labeled_reviews_mvp_for_training.csv` используется как основной train set.

---

### `generate_manual_check_random_by_class.ipynb`

Формирует выборку для ручной проверки качества разметки.

На вход использует данные, разложенные по классам:

```text
data/labeled/wb_feedbacks_by_class_with_synthetic/
```

Ноутбук выбирает случайные примеры по каждому классу и собирает единый файл для manual check.

Выход:

```text
data/labeled/wb_feedbacks_manual_check_random/
manual_check_random_by_class.csv
```

Дополнительно сохраняется сводка:

```text
manual_check_random_summary.csv
```

После ручного заполнения `correct_labels`, `comment`, `is_correct` эта выборка используется как основа golden set.

---

### `ChatGpt_markup_gpt5_manual_check_only.ipynb`

Повторно размечает через GPT-5 только manual-check примеры.

На вход использует файл ручной проверки:

```text
data/labeled/wb_feedbacks_manual_check_random_v1/
manual_check_random_by_class.csv
```

Для разметки используется:

```text
gpt-5
```

На выходе формируется файл, где можно сопоставить старую разметку, новую GPT-5-разметку и ручные `correct_labels`:

```text
data/labeled/wb_feedbacks_manual_check_random_gpt5_prompt_test_v5/
manual_check_random_by_class_gpt5_relabelled.csv
```

Также сохраняются:

```text
manual_check_random_by_class_gpt5_errors_only.csv
manual_check_random_by_class_gpt5_summary.csv
```

Этот этап нужен для проверки качества промпта и подготовки финального golden set для оценки классификатора.

## Итоговые артефакты

Основной train set:

```text
data/labeled/wb_feedbacks_ChatGpt_markup_from_synthetic_gpt5_V_2/
chatgpt_labeled_reviews_mvp_for_training.csv
```

Основной combined-файл с GPT-5-разметкой:

```text
data/labeled/wb_feedbacks_ChatGpt_markup_from_synthetic_gpt5_V_2/
chatgpt_labeled_reviews_mvp_combined.csv
```

Golden set / manual-check файл:

```text
data/labeled/wb_feedbacks_manual_check_random_gpt5_prompt_test_v5/
manual_check_random_by_class_gpt5_relabelled.csv
```

## Краткая последовательность запуска

```text
1. dataset_downloading.ipynb
2. makes_200_000_random_samples_from_100_chunks.ipynb
3. data_markup.ipynb
4. generate_by_class_with_synthetic.ipynb
5. ChatGpt_markup_gpt5_from_synthetic.ipynb
6. generate_manual_check_random_by_class.ipynb
7. ChatGpt_markup_gpt5_manual_check_only.ipynb
```

После этих этапов есть две основные сущности: train set для обучения модели и golden set для оценки ее качества.
