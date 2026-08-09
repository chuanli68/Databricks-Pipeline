-- ============================================================
-- Teardown — removes everything the prototype created.
-- Run only when you want to start clean or free up your Free Edition quota.
-- ============================================================
DROP CATALOG IF EXISTS pubmkt_bronze CASCADE;
DROP CATALOG IF EXISTS pubmkt_silver CASCADE;
DROP CATALOG IF EXISTS pubmkt_gold   CASCADE;
DROP CATALOG IF EXISTS pvtmkt_bronze CASCADE;
DROP CATALOG IF EXISTS pvtmkt_silver CASCADE;
DROP CATALOG IF EXISTS pvtmkt_gold   CASCADE;
DROP CATALOG IF EXISTS ref_master    CASCADE;
DROP CATALOG IF EXISTS edw_meta      CASCADE;

SELECT 'teardown complete' AS status;

-- To reset ONLY the data but keep catalogs (re-run from step 2 afterwards):
-- DROP TABLE IF EXISTS pubmkt_bronze.bloomberg.eod_prices;
-- DROP TABLE IF EXISTS pubmkt_bronze.refinitiv.eod_prices;
-- DROP TABLE IF EXISTS pubmkt_bronze.internal.positions;
-- DROP TABLE IF EXISTS pvtmkt_bronze.efront.fund_valuations;
-- DROP TABLE IF EXISTS pvtmkt_bronze.dealcloud.deals;
-- DROP SCHEMA IF EXISTS pubmkt_silver.instrument CASCADE;
-- DROP SCHEMA IF EXISTS pubmkt_silver.conformed  CASCADE;
-- DROP SCHEMA IF EXISTS pvtmkt_silver.fund       CASCADE;
-- DROP SCHEMA IF EXISTS pvtmkt_silver.conformed  CASCADE;
-- DROP SCHEMA IF EXISTS ref_master.instrument    CASCADE;
