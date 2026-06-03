-- Migration: 003_create_review_embeddings
-- 목적: 리뷰 텍스트 청크 임베딩 테이블 + HNSW + product_id 인덱스
-- 의존: pgvector 확장, products 테이블

CREATE TABLE IF NOT EXISTS review_embeddings (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id   UUID         NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    review_text  TEXT         NOT NULL,
    embedding    vector(1024) NOT NULL,
    source       VARCHAR(50)  NOT NULL,
    created_at   TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_embeddings_product
    ON review_embeddings (product_id);

CREATE INDEX IF NOT EXISTS idx_review_embeddings_hnsw
    ON review_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE review_embeddings IS '리뷰 텍스트 청크의 bge-m3 임베딩. score_agent의 review_score 계산에 사용';
COMMENT ON COLUMN review_embeddings.source IS '출처. 예: OLIVEYOUNG | NAVER | GEMINI_EXTRACTED';