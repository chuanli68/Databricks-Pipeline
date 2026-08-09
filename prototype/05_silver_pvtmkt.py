# Databricks notebook source
# ============================================================
# GENERATED-STYLE CODE (prototype) — private markets silver.
# provenance: mapping=pvtmkt.efront.fund_valuations__fund v1.0.0
# Org-specific hub (fund) lives inside pvtmkt_silver (doc 05 §2).
# Idempotent: safe to re-run.
# ============================================================

# COMMAND ----------

# MAGIC %run ./edw_lib

# COMMAND ----------

from pyspark.sql import functions as F

HUB = "pvtmkt_silver.fund.h_fund"
KM  = "pvtmkt_silver.fund.km_fund"

# ---------- entity: fund | source: efront ----------
fv = spark.table("pvtmkt_bronze.efront.fund_valuations")
upsert_hub_keymap(spark, fv, HUB, KM, "fund",
                  business_key_col="fund_code", source_system="efront", source_key_col="fund_code")

staged = (fv.alias("s")
    .join(spark.table(KM).where("source_system='efront'").alias("k"),
          F.col("s.fund_code") == F.col("k.source_key"))
    .select(
        F.col("k.fund_hk"),
        F.trim("s.fund_name").alias("fund_name"),
        F.col("s.vintage"),
        F.upper("s.currency").alias("currency"),
        F.col("s.asset_class"),
        F.col("s.nav_musd"),
        F.col("s.valuation_date"),
        F.col("s._load_ts")))

# descriptive attributes -> one current row per fund
load_satellite(spark,
    staged.select("fund_hk", "fund_name", "vintage", "currency", "asset_class",
                  "valuation_date", "_load_ts"),
    "pvtmkt_silver.fund.s_fund__efront", "fund",
    hash_cols=["fund_name", "vintage", "currency", "asset_class"],
    effective_from_col="valuation_date", record_source="pvtmkt.efront.fund_valuations")

# NAV per valuation period -> multi-active; a restated NAV versions only that period,
# which is exactly the audit trail a NAV restatement requires.
load_satellite(spark,
    staged.select("fund_hk", "valuation_date", "nav_musd", "_load_ts"),
    "pvtmkt_silver.fund.s_fund_nav__efront", "fund",
    hash_cols=["nav_musd"], subkeys=["valuation_date"],
    effective_from_col="valuation_date", record_source="pvtmkt.efront.fund_valuations")

# ---------- Tier-3 conformed: dealcloud deals ----------
load_conformed(spark, "pvtmkt_bronze.dealcloud.deals",
               "pvtmkt_silver.conformed.dealcloud__deals",
               dedup_keys=["deal_id"], order_by="_load_ts DESC")

# ---------- generated current view ----------
spark.sql("""
CREATE OR REPLACE VIEW pvtmkt_silver.fund.v_fund_current AS
WITH latest_nav AS (
  SELECT fund_hk, valuation_date, nav_musd,
         ROW_NUMBER() OVER (PARTITION BY fund_hk ORDER BY valuation_date DESC) AS rn
  FROM pvtmkt_silver.fund.s_fund_nav__efront WHERE is_current
)
SELECT h.fund_hk, h.business_key AS fund_code,
       s.fund_name, s.vintage, s.currency, s.asset_class,
       n.nav_musd, n.valuation_date, s.record_source
FROM pvtmkt_silver.fund.h_fund h
JOIN pvtmkt_silver.fund.s_fund__efront s ON s.fund_hk = h.fund_hk AND s.is_current
LEFT JOIN latest_nav n ON n.fund_hk = h.fund_hk AND n.rn = 1
""")

log_run(spark, "silver_pvtmkt", "OK", "fund hub + descriptive sat + nav sat + conformed deals + view")
print("pvtmkt silver loaded.")
