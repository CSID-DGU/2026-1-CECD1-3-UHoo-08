-- Migration: 006_rpc_match_alternatives
-- 목적: alternative_agent의 대체 상품 검색 RPC
-- 의존: product_embeddings, products

CREATE OR REPLACE FUNCTION match_alternatives(
    base_product_id UUID,
    match_count     INT    DEFAULT 5,
    exclude_ids     UUID[] DEFAULT '{}'
)
RETURNS TABLE (
    product_id  UUID,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
    base_vec      vector(1024);
    base_category VARCHAR;
BEGIN
    PERFORM set_config('hnsw.ef_search', '40', true);

    SELECT pe.feature_vec, p.category
      INTO base_vec, base_category
    FROM product_embeddings pe
    JOIN products p ON p.product_id = pe.product_id
    WHERE pe.product_id = base_product_id;

    IF base_vec IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        pe.product_id,
        1 - (pe.feature_vec <=> base_vec) AS similarity
    FROM product_embeddings pe
    JOIN products p ON p.product_id = pe.product_id
    WHERE
        p.category = base_category
        AND pe.product_id <> base_product_id
        AND pe.product_id <> ALL(exclude_ids)
    ORDER BY pe.feature_vec <=> base_vec
    LIMIT match_count;
END;
$$;

GRANT EXECUTE ON FUNCTION match_alternatives(UUID, INT, UUID[]) TO service_role;

COMMENT ON FUNCTION match_alternatives IS '기준 상품의 feature_vec과 유사한 같은 카테고리 대체 상품 검색';