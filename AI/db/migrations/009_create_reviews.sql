-- Migration: 009_create_reviews
-- 목적: 리뷰 원본 텍스트 저장. review_embeddings의 단일 소스.
-- 의존: products 테이블 (PK: product_id)

CREATE TABLE IF NOT EXISTS reviews (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id  UUID         NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    content     TEXT         NOT NULL,
    rating      INT,                        -- 1~5, 없으면 NULL
    source      VARCHAR(50)  NOT NULL,      -- OLIVEYOUNG | NAVER | GEMINI_SYNTHETIC 등
    author      VARCHAR(100),               -- 작성자 닉네임 (선택)
    created_at  TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reviews_product
    ON reviews (product_id);

COMMENT ON TABLE reviews IS '리뷰 원본 텍스트. reembed_reviews가 청크·임베딩해 review_embeddings로 적재';
COMMENT ON COLUMN reviews.rating IS '1~5 평점. 없으면 NULL';
COMMENT ON COLUMN reviews.source IS '출처. OLIVEYOUNG | NAVER | GEMINI_SYNTHETIC 등';