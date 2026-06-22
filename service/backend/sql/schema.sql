-- Минимальная схема под online-сервис.
-- Ее можно адаптировать под реальные колонки из датасета Wildberries.

CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    review_date DATE,
    text TEXT NOT NULL,
    rating INTEGER,
    product_id TEXT,
    product_name TEXT,
    brand TEXT,
    category TEXT,
    seller_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_labels (
    review_id TEXT NOT NULL REFERENCES reviews(review_id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    model_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (review_id, label)
);

CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(review_date);
CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_brand ON reviews(brand);
CREATE INDEX IF NOT EXISTS idx_reviews_category ON reviews(category);
CREATE INDEX IF NOT EXISTS idx_reviews_seller ON reviews(seller_id);
CREATE INDEX IF NOT EXISTS idx_review_labels_label ON review_labels(label);
