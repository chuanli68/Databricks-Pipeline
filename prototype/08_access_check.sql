-- ============================================================
-- Access-control verification (runbook R9, scaled down)
-- ============================================================

-- A. Inspect grants (works even single-user): each statement should show
--    ONLY the intended principal and privileges.
SHOW GRANTS ON CATALOG pubmkt_gold;
SHOW GRANTS ON CATALOG pvtmkt_gold;
SHOW GRANTS ON SCHEMA  ref_master.reference;
SHOW GRANTS ON CATALOG pubmkt_bronze;   -- expect: no analyst grants at all
SHOW GRANTS ON CATALOG pvtmkt_silver;   -- expect: no analyst grants at all

-- B. The barrier audit query (doc 05 §6): grants on org catalogs to
--    principals outside the org. Expect ZERO unexpected rows.
--    (On Free Edition run per-catalog SHOW GRANTS above; with system tables:)
-- SELECT * FROM system.information_schema.catalog_privileges
-- WHERE catalog_name LIKE 'pvtmkt%' AND grantee LIKE '%pubmkt%'
--    OR catalog_name LIKE 'pubmkt%' AND grantee LIKE '%pvtmkt%';

-- C. Live test — run these AS THE SECOND USER (pubmkt analyst login):
--    1. Should succeed:
-- SELECT * FROM pubmkt_gold.risk_snapshot.v_daily_position_risk LIMIT 5;
-- SELECT * FROM ref_master.reference.asset_class;
--    2. Should fail with PERMISSION_DENIED / catalog not found:
-- SELECT * FROM pvtmkt_gold.fund_performance.v_fund_nav_history LIMIT 5;
-- SHOW CATALOGS;  -- pvtmkt_* should not appear
