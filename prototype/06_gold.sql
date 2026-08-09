-- ============================================================
-- GENERATED-STYLE CODE (prototype) — gold projections (A5 output).
-- provenance: use-case=daily_pm_risk_snapshot v1.0.0, fund_performance v1.0.0
-- Gold reads ONLY silver current views + satellites + shared reference.
-- ============================================================

-- ---------- pubmkt use case: daily position risk ----------
-- positions valued at the price of the SAME date (uses the price time-series satellite)
CREATE OR REPLACE VIEW pubmkt_gold.risk_snapshot.v_daily_position_risk AS
SELECT
  p.position_date,
  p.portfolio_id,
  i.isin,
  i.name                             AS instrument_name,
  i.currency,
  coalesce(ac.name, i.sector_raw)    AS asset_class_name,   -- shared reference join
  coalesce(ac.bucket, 'UNMAPPED')    AS asset_bucket,
  p.qty,
  px.close_px,
  round(p.qty * px.close_px, 2)      AS market_value_local
FROM pubmkt_silver.conformed.internal__positions p
JOIN pubmkt_silver.instrument.v_instrument_current i ON i.isin = p.isin
JOIN pubmkt_silver.instrument.v_instrument_price px
  ON px.instrument_hk = i.instrument_hk AND px.price_date = p.position_date
LEFT JOIN ref_master.reference.asset_class ac
  ON ac.code = CASE
       WHEN i.sector_raw IN ('Govt','Sovereign','GOVT','SOVEREIGN') THEN 'FI_SOV'
       WHEN i.sector_raw IN ('Corp Bond','CORP BOND')               THEN 'FI_CRD'
       ELSE 'EQ_DM' END;

-- price history including restatements (SCD2 versions visible)
CREATE OR REPLACE VIEW pubmkt_gold.risk_snapshot.v_price_history AS
SELECT h.business_key AS isin, s.price_date, s.close_px,
       s.effective_from, s.effective_to, s.is_current, s.record_source
FROM pubmkt_silver.instrument.s_instrument_price__bloomberg s
JOIN ref_master.instrument.h_instrument h ON h.instrument_hk = s.instrument_hk;

-- ---------- pvtmkt use case: fund performance ----------
CREATE OR REPLACE VIEW pvtmkt_gold.fund_performance.v_fund_nav_history AS
SELECT
  f.business_key                     AS fund_code,
  d.fund_name,
  d.vintage,
  d.currency,
  ac.name                            AS asset_class_name,   -- shared reference join
  n.nav_musd,
  n.valuation_date,
  n.effective_from,
  n.effective_to,
  n.is_current                       -- false = superseded by a restatement
FROM pvtmkt_silver.fund.h_fund f
JOIN pvtmkt_silver.fund.s_fund_nav__efront n ON n.fund_hk = f.fund_hk
JOIN pvtmkt_silver.fund.s_fund__efront d ON d.fund_hk = f.fund_hk AND d.is_current
LEFT JOIN ref_master.reference.asset_class ac ON ac.code = d.asset_class;

CREATE OR REPLACE VIEW pvtmkt_gold.fund_performance.v_deal_pipeline AS
SELECT d.deal_id, d.deal_name, d.fund_code, fc.fund_name,
       d.sector, d.deal_size_musd, d.status, d.signed_date
FROM pvtmkt_silver.conformed.dealcloud__deals d
LEFT JOIN pvtmkt_silver.fund.v_fund_current fc ON fc.fund_code = d.fund_code;

SELECT 'gold views created' AS status;
