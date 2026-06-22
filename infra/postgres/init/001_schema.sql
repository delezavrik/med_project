CREATE TABLE IF NOT EXISTS reviews (
    review_id BIGINT PRIMARY KEY,
    review_text TEXT NOT NULL,
    predicted_labels JSONB NOT NULL DEFAULT '[]'::jsonb,
    predicted_labels_str TEXT,

    rating DOUBLE PRECISION,
    category TEXT,
    subject TEXT,
    brand TEXT,
    product_id TEXT,
    product_name TEXT,
    seller_id TEXT,
    nm_id TEXT,
    imt_id TEXT,
    supplier_id TEXT,
    feedback_id TEXT,
    review_date TIMESTAMPTZ,

    source_dataset TEXT,
    text_column_source TEXT,
    classifier_embedding_model TEXT,
    classifier_model TEXT,
    raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    inserted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews (rating);
CREATE INDEX IF NOT EXISTS idx_reviews_category ON reviews (category);
CREATE INDEX IF NOT EXISTS idx_reviews_subject ON reviews (subject);
CREATE INDEX IF NOT EXISTS idx_reviews_brand ON reviews (brand);
CREATE INDEX IF NOT EXISTS idx_reviews_nm_id ON reviews (nm_id);
CREATE INDEX IF NOT EXISTS idx_reviews_labels_gin ON reviews USING GIN (predicted_labels);
CREATE INDEX IF NOT EXISTS idx_reviews_raw_metadata_gin ON reviews USING GIN (raw_metadata);

-- Для простого текстового поиска в PostgreSQL. Для основного RAG используется Qdrant.
CREATE INDEX IF NOT EXISTS idx_reviews_text_ru_gin
ON reviews USING GIN (to_tsvector('russian', coalesce(review_text, '')));
