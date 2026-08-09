-- ============================================================
-- Prototype step 0: catalogs & schemas (doc 05 layout, scaled down)
-- Run in a SQL editor or notebook on Databricks Free Edition.
-- ============================================================

-- Org: public markets
CREATE CATALOG IF NOT EXISTS pubmkt_bronze;
CREATE SCHEMA  IF NOT EXISTS pubmkt_bronze.bloomberg;
CREATE SCHEMA  IF NOT EXISTS pubmkt_bronze.refinitiv;
CREATE SCHEMA  IF NOT EXISTS pubmkt_bronze.internal;

CREATE CATALOG IF NOT EXISTS pubmkt_silver;
CREATE SCHEMA  IF NOT EXISTS pubmkt_silver.instrument;   -- Tier-1 subject area (sats live here; shared hub in ref_master)
CREATE SCHEMA  IF NOT EXISTS pubmkt_silver.conformed;    -- Tier-3

CREATE CATALOG IF NOT EXISTS pubmkt_gold;
CREATE SCHEMA  IF NOT EXISTS pubmkt_gold.risk_snapshot;

-- Org: private markets
CREATE CATALOG IF NOT EXISTS pvtmkt_bronze;
CREATE SCHEMA  IF NOT EXISTS pvtmkt_bronze.efront;
CREATE SCHEMA  IF NOT EXISTS pvtmkt_bronze.dealcloud;

CREATE CATALOG IF NOT EXISTS pvtmkt_silver;
CREATE SCHEMA  IF NOT EXISTS pvtmkt_silver.fund;         -- Tier-1 (org-specific hub lives here)
CREATE SCHEMA  IF NOT EXISTS pvtmkt_silver.conformed;    -- Tier-3

CREATE CATALOG IF NOT EXISTS pvtmkt_gold;
CREATE SCHEMA  IF NOT EXISTS pvtmkt_gold.fund_performance;

-- Shared: cross-org identity + reference data (the ONLY cross-org surface, ADR-5)
CREATE CATALOG IF NOT EXISTS ref_master;
CREATE SCHEMA  IF NOT EXISTS ref_master.instrument;      -- shared hub + key map
CREATE SCHEMA  IF NOT EXISTS ref_master.reference;       -- shared reference data

-- Platform: operational state
CREATE CATALOG IF NOT EXISTS edw_meta;
CREATE SCHEMA  IF NOT EXISTS edw_meta.ops;

CREATE TABLE IF NOT EXISTS edw_meta.ops.run_ledger (
  run_ts        TIMESTAMP,
  component     STRING,
  status        STRING,
  detail        STRING
);

-- Seed shared reference data (normally its own governed feed)
CREATE OR REPLACE TABLE ref_master.reference.asset_class (
  code STRING NOT NULL, name STRING, bucket STRING
);
INSERT INTO ref_master.reference.asset_class VALUES
  ('EQ_DM',  'Developed Market Equity',  'EQUITY'),
  ('EQ_EM',  'Emerging Market Equity',   'EQUITY'),
  ('FI_SOV', 'Sovereign Fixed Income',   'FIXED_INCOME'),
  ('FI_CRD', 'Credit',                   'FIXED_INCOME'),
  ('PE_BO',  'Private Equity Buyout',    'PRIVATE'),
  ('PE_GR',  'Private Equity Growth',    'PRIVATE'),
  ('RE_CORE','Core Real Estate',         'PRIVATE');

CREATE OR REPLACE TABLE ref_master.reference.currency (
  code STRING NOT NULL, name STRING
);
INSERT INTO ref_master.reference.currency VALUES
  ('USD','US Dollar'), ('SGD','Singapore Dollar'), ('EUR','Euro'),
  ('JPY','Japanese Yen'), ('GBP','Pound Sterling');

SELECT 'setup complete' AS status;
