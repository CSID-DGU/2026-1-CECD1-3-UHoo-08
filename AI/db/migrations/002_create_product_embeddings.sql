-- Migration: 002_create_product_embeddings
-- 목적: 상품 feature 임베딩 테이블 + HNSW 인덱스
-- 의존: pgvector 확장, products 테이블

CREATE TABLE IF NOT EXISTS product_embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id      UUID         NOT NULL UNIQUE REFERENCES products(product_id) ON DELETE CASCADE,
    feature_vec     vector(1024) NOT NULL,
    model_version   VARCHAR(50)  NOT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_embeddings_hnsw
    ON product_embeddings
    USING hnsw (feature_vec vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE product_embeddings IS '상품 feature_json을 자연어로 변환 후 bge-m3로 임베딩한 1024차원 벡터';
COMMENT ON COLUMN product_embeddings.feature_vec IS 'L2 정규화된 1024차원 임베딩';
COMMENT ON COLUMN product_embeddings.model_version IS '예: bge-m3-v1.5. 모델 교체 시 점진 마이그레이션 식별자';