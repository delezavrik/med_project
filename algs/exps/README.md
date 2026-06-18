# `exps`: эксперименты классификации отзывов

Папка содержит ноутбуки с экспериментами по multi-label классификации отзывов покупателей. Основная задача — по тексту отзыва определить один или несколько проблемных классов: качество товара, размер/посадка, доставка, возврат, несоответствие карточке товара, цена/ценность и другие категории.

В экспериментах используются два набора данных:

```text
train dataset:
data/labeled/wb_feedbacks_ChatGpt_markup_from_synthetic_gpt5_V_2/
chatgpt_labeled_reviews_mvp_combined.csv

оценочная выборка / golden set:
data/labeled/wb_feedbacks_manual_check_random_gpt5_prompt_test_v5/
manual_check_random_by_class_gpt5_relabelled.csv
```

Train set был сформирован на предыдущем этапе через GPT-5-разметку real + synthetic корзинки. Golden set — это случайное подмножество примеров, отобранное из GPT-5-размеченных данных и затем проверенное вручную.

---

## Структура папки

```text
exps/
├── README.md
├── embedding_model/
│   ├── embedding_classifier_experiments_reviews.ipynb
│   ├── embedding_classifier_selected_3_thresholds.ipynb
│   └── analyze/
│       └── embedding_classifier_results_analysis.ipynb
├── fine_tune_model/
│   ├── rubert_frozen_encoder_multilabel_reviews.ipynb
│   └── analyze/
│       └── rubert_frozen_encoder_results_analysis.ipynb
└── analyze/
    └── README.md
```

---

## Верхнеуровневый пайплайн

```text
GPT-5 train dataset + golden set
        ↓
1. Embedding experiments
        ↓
перебор embedding-моделей и классических классификаторов
        ↓
2. Threshold tuning для лучших embedding-моделей
        ↓
финальный embedding-классификатор

GPT-5 train dataset + golden set
        ↓
3. RuBERT frozen encoder experiment
        ↓
замороженный RuBERT + обучаемая классификационная голова
        ↓
сравнение с embedding-подходом

результаты embedding + RuBERT
        ↓
4. analyze notebooks + summary README
        ↓
итоговый анализ метрик и выбор лучшего подхода
```

---

# 1. `embedding_model/`

Эта папка содержит основную ветку экспериментов: готовые embedding-модели используются как извлекатель признаков, а сверху обучаются классические multi-label классификаторы.

## `embedding_classifier_experiments_reviews.ipynb`

Первый основной эксперимент с embedding-моделями.

### Что делает

Ноутбук загружает train dataset и golden set, строит эмбеддинги для текстов отзывов и обучает несколько классических классификаторов поверх этих эмбеддингов.

### Используемые embedding-модели

```text
USER-bge-m3              -> deepvk/USER-bge-m3
bge-m3                  -> BAAI/bge-m3
ru-en-RoSBERTa          -> ai-forever/ru-en-RoSBERTa
multilingual-e5-base    -> intfloat/multilingual-e5-base
```

### Используемые классификаторы

```text
LinearSVC_balanced
Ridge_balanced
SGD_hinge_balanced
SGD_logloss_balanced
LogReg_balanced
RandomForest_balanced
ExtraTrees_balanced
```

### Что сохраняет

Результаты сохраняются в директорию:

```text
data/labeled/embedding_classifier_experiments/
```

Основные выходные файлы:

```text
summary_metrics.csv
per_class_metrics.csv
```

Дополнительно сохраняются кэши эмбеддингов и обученные модели.

### Роль в пайплайне

Этот ноутбук нужен для широкого перебора конфигураций и выбора лучших связок embedding-модель + классификатор. На этом этапе определяется, какие модели стоит дополнительно проверять с подбором индивидуальных thresholds по классам.

---

## `embedding_classifier_selected_3_thresholds.ipynb`

Второй embedding-эксперимент: углубленная проверка трех лучших моделей.

### Что делает

После общего перебора выбираются три сильные конфигурации:

```text
bge-m3 + LinearSVC_balanced
bge-m3 + SGD_hinge_balanced
USER-bge-m3 + Ridge_balanced
```

Для каждой из них сравниваются два режима:

```text
baseline     — стандартное решение классификатора;
thresholded  — отдельный threshold для каждого класса.
```

Threshold tuning нужен, потому что разные классы имеют разную частоту и разную уверенность модели. Один общий порог для всех классов может быть не оптимален.

### Что сохраняет

Результаты сохраняются в ту же директорию:

```text
data/labeled/embedding_classifier_experiments/
```

Основные выходные файлы:

```text
summary_metrics_selected_baseline.csv
per_class_metrics_selected_baseline.csv

summary_metrics_selected_thresholded.csv
per_class_metrics_selected_thresholded.csv

summary_metrics_selected_combined.csv
per_class_metrics_selected_combined.csv
```

Файлы с подобранными порогами:

```text
bge-m3__LinearSVC_balanced__thresholds.csv
bge-m3__SGD_hinge_balanced__thresholds.csv
USER-bge-m3__Ridge_balanced__thresholds.csv
```

### Роль в пайплайне

Этот ноутбук нужен для финального выбора embedding-модели. Он показывает, улучшает ли качество подбор отдельных thresholds по классам и какая конфигурация дает лучший баланс precision/recall/F1.

---

## `embedding_model/analyze/embedding_classifier_results_analysis.ipynb`

Ноутбук для просмотра и интерпретации результатов embedding-экспериментов.

### Что делает

Он не обучает модели заново. Его задача — красиво вывести и проанализировать уже сохраненные CSV с метриками.

В ноутбуке показываются:

```text
топ моделей по macro_f1;
сравнение baseline vs thresholded;
изменение precision / recall после threshold tuning;
per-class метрики лучшей модели;
проблемные классы;
подобранные thresholds;
итоговый выбор модели.
```

### Роль в пайплайне

Это отчетный ноутбук для embedding-ветки. Он нужен, чтобы быстро открыть результаты экспериментов без повторного обучения моделей.

---

# 2. `fine_tune_model/`

Эта папка содержит нейросетевой эксперимент с RuBERT. В отличие от embedding-подхода, здесь используется transformer encoder `DeepPavlov/rubert-base-cased`, а сверху обучается классификационная голова.

## `rubert_frozen_encoder_multilabel_reviews.ipynb`

Эксперимент с RuBERT frozen encoder.

### Что делает

Ноутбук загружает train dataset и golden set, извлекает признаки текстов через RuBERT и обучает multi-label классификационную голову.

Encoder RuBERT заморожен: его веса не дообучаются. Обучается только верхняя классификационная голова.

### Используемая модель

```text
DeepPavlov/rubert-base-cased
```

### Основные этапы

```text
1. Загрузка train и golden set
2. Нормализация текстов и labels
3. Train / validation split
4. Извлечение CLS-признаков из RuBERT
5. Обучение линейной головы
6. Подбор thresholds по validation set
7. Оценка на golden set
8. Сохранение summary и per-class метрик
```

### Что сохраняет

Результаты сохраняются в директорию:

```text
data/labeled/rubert_frozen_encoder_experiment/
```

Основные выходные файлы:

```text
summary_metrics_rubert_frozen_encoder.csv
per_class_metrics_rubert_frozen_encoder.csv
rubert_frozen_encoder_thresholds.csv
training_history.csv
```

Дополнительно сохраняются:

```text
features_cache/
trained_model/
plots/
```

### Роль в пайплайне

Этот ноутбук нужен как нейросетевой baseline для сравнения с embedding-подходом. Он проверяет, достаточно ли замороженного RuBERT encoder и небольшой обучаемой головы для решения задачи multi-label классификации отзывов.

---

## `fine_tune_model/analyze/rubert_frozen_encoder_results_analysis.ipynb`

Ноутбук для анализа результатов RuBERT frozen encoder.

### Что делает

Он не обучает модель заново, а загружает сохраненные результаты эксперимента и выводит их в удобном виде.

В ноутбуке показываются:

```text
summary-метрики RuBERT;
сравнение threshold = 0.5 и tuned thresholds;
динамика обучения по эпохам;
подобранные thresholds по классам;
per-class качество;
классы, на которых модель работает лучше и хуже;
итоговый вывод по RuBERT-подходу.
```

### Роль в пайплайне

Это отчетный ноутбук для RuBERT-ветки. Он нужен для интерпретации метрик и сравнения RuBERT frozen encoder с embedding-классификаторами.

---

# 3. `analyze/`

Папка содержит общий анализ результатов.

## `analyze/README.md`

Файл объединяет выводы по нескольким экспериментам.

### Что описывает

```text
1. Общий перебор embedding-моделей и классификаторов
2. Threshold tuning для трех лучших embedding-конфигураций
3. RuBERT frozen encoder
4. RuBERT head-only classifier
5. Сравнение подходов между собой
6. Итоговый выбор модели
```

### Роль в пайплайне

Это итоговый отчет по экспериментам. Его можно использовать как краткое текстовое описание результатов для README проекта, отчета или защиты.

---

# Итоговая связь файлов

```text
embedding_classifier_experiments_reviews.ipynb
        ↓
широкий перебор embedding-моделей и классификаторов
        ↓
summary_metrics.csv + per_class_metrics.csv
        ↓
embedding_classifier_selected_3_thresholds.ipynb
        ↓
проверка трех лучших моделей + threshold tuning
        ↓
summary_metrics_selected_*.csv + thresholds.csv
        ↓
embedding_classifier_results_analysis.ipynb
        ↓
анализ и выбор лучшей embedding-модели
```

```text
rubert_frozen_encoder_multilabel_reviews.ipynb
        ↓
обучение RuBERT frozen encoder + linear head
        ↓
summary_metrics_rubert_frozen_encoder.csv
per_class_metrics_rubert_frozen_encoder.csv
training_history.csv
thresholds.csv
        ↓
rubert_frozen_encoder_results_analysis.ipynb
        ↓
анализ качества RuBERT-подхода
```

```text
embedding-анализ + RuBERT-анализ
        ↓
analyze/README.md
        ↓
общий вывод по экспериментам
```

---

# Краткий итог по смыслу экспериментов

В папке `exps` проверяются два подхода к классификации отзывов.

Первый подход — embedding-модели + классические классификаторы. Он оказался основным и наиболее сильным: готовые sentence embeddings хорошо кодируют смысл отзыва, а линейные классификаторы уверенно разделяют классы.

Второй подход — RuBERT frozen encoder + обучаемая голова. Он используется как нейросетевой baseline. Поскольку encoder заморожен и не дообучается под задачу, качество оказалось ниже, чем у embedding-подхода.

Итоговая логика экспериментов: сначала перебрать много конфигураций, затем детально проверить лучшие варианты, подобрать thresholds по классам и сравнить итоговое качество с RuBERT baseline.
