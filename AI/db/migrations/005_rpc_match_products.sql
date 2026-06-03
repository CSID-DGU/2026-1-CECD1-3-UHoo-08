-- Migration: 005_rpc_match_products
-- 목적: discovery_agent의 후보 상품 검색 RPC
-- 의존: product_embeddings, products

CREATE OR REPLACE FUNCTION match_products(
    query_embedding vector(1024),
    match_category  VARCHAR DEFAULT NULL,
    match_count     INT     DEFAULT 20,
    exclude_ids     UUID[]  DEFAULT '{}'
)
RETURNS TABLE (
    product_id  UUID,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM set_config('hnsw.ef_search', '40', true);

    RETURN QUERY
    SELECT
        pe.product_id,
        1 - (pe.feature_vec <=> query_embedding) AS similarity
    FROM product_embeddings pe
    JOIN products p ON p.product_id = pe.product_id
    WHERE
        (match_category IS NULL OR p.category = match_category)
        AND pe.product_id <> ALL(exclude_ids)
    ORDER BY pe.feature_vec <=> query_embedding
    LIMIT match_count;
END;
$$;

GRANT EXECUTE ON FUNCTION match_products(vector, VARCHAR, INT, UUID[]) TO service_role;

COMMENT ON FUNCTION match_products IS 'intent_vector와 유사한 후보 상품 검색. discovery_agent에서 사용';