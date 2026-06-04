-- ============================================================
-- Table Consolidation Migration
-- 1. user_skin_profiles + user_preferences + price_tracking_alert_settings → users
-- 2. product_features + product_insights → products
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- STEP 1: Add new columns to users
-- ──────────────────────────────────────────────────────────────

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS personal_color     VARCHAR(20),
    ADD COLUMN IF NOT EXISTS skin_type          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS skin_concerns      TEXT[]        DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS notes              TEXT[],
    ADD COLUMN IF NOT EXISTS search_purpose     VARCHAR(20),
    ADD COLUMN IF NOT EXISTS price_tolerance_percent INTEGER,
    ADD COLUMN IF NOT EXISTS target_price_alert BOOLEAN       NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS weekly_report      BOOLEAN       NOT NULL DEFAULT FALSE;

-- ──────────────────────────────────────────────────────────────
-- STEP 2: Migrate data from user_skin_profiles → users
-- ──────────────────────────────────────────────────────────────

UPDATE users u
SET
    personal_color = usp.personal_color,
    skin_type      = usp.skin_type,
    skin_concerns  = usp.skin_concerns,
    notes          = usp.notes
FROM user_skin_profiles usp
WHERE usp.user_id = u.id;

-- ──────────────────────────────────────────────────────────────
-- STEP 3: Migrate data from user_preferences → users
-- ──────────────────────────────────────────────────────────────

UPDATE users u
SET
    search_purpose           = up.search_purpose,
    price_tolerance_percent  = up.price_tolerance_percent
FROM user_preferences up
WHERE up.user_id = u.id;

-- ──────────────────────────────────────────────────────────────
-- STEP 4: Migrate data from price_tracking_alert_settings → users
-- ──────────────────────────────────────────────────────────────

UPDATE users u
SET
    target_price_alert = ptas.target_price_alert,
    weekly_report      = ptas.weekly_report
FROM price_tracking_alert_settings ptas
WHERE ptas.user_id = u.id;

-- ──────────────────────────────────────────────────────────────
-- STEP 5: Drop old user-related tables
-- ──────────────────────────────────────────────────────────────

DROP TABLE IF EXISTS price_tracking_alert_settings;
DROP TABLE IF EXISTS user_preferences;
DROP TABLE IF EXISTS user_skin_profiles;

-- ──────────────────────────────────────────────────────────────
-- STEP 6: Add new columns to products
-- ──────────────────────────────────────────────────────────────

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS feature_json           JSONB,
    ADD COLUMN IF NOT EXISTS lowest_price           INTEGER,
    ADD COLUMN IF NOT EXISTS savings                INTEGER,
    ADD COLUMN IF NOT EXISTS stores                 JSONB,
    ADD COLUMN IF NOT EXISTS review_summary         TEXT,
    ADD COLUMN IF NOT EXISTS average_score          NUMERIC(3, 1),
    ADD COLUMN IF NOT EXISTS review_count           INTEGER,
    ADD COLUMN IF NOT EXISTS skin_type_satisfaction JSONB,
    ADD COLUMN IF NOT EXISTS last_updated_at        TIMESTAMP WITH TIME ZONE;

-- ──────────────────────────────────────────────────────────────
-- STEP 7: Migrate data from product_features → products
-- ──────────────────────────────────────────────────────────────

UPDATE products p
SET feature_json = pf.feature_json
FROM product_features pf
WHERE pf.product_id = p.product_id;

-- ──────────────────────────────────────────────────────────────
-- STEP 8: Migrate data from product_insights → products
-- ──────────────────────────────────────────────────────────────

UPDATE products p
SET
    lowest_price           = pi.lowest_price,
    savings                = pi.savings,
    stores                 = pi.stores::jsonb,
    review_summary         = pi.review_summary,
    average_score          = pi.average_score,
    review_count           = pi.review_count,
    skin_type_satisfaction = pi.skin_type_satisfaction::jsonb,
    last_updated_at        = pi.last_updated_at
FROM product_insights pi
WHERE pi.product_id = p.product_id;

-- ──────────────────────────────────────────────────────────────
-- STEP 9: Drop old product-related tables
-- ──────────────────────────────────────────────────────────────

DROP TABLE IF EXISTS product_features;
DROP TABLE IF EXISTS product_insights;
