# Databricks notebook source
# ============================================================
# GENERATED-STYLE CODE (prototype). In production each block below is a
# separate file rendered from mapping.yml by satellite_merge.sql.j2 etc.
# provenance: mapping=pubmkt.bloomberg.eod_prices__instrument v1.1.0,
#             template=satellite_merge v1, renderer=prototype-hand-render
#
# Two satellite kinds per source (see edw_lib.load_satellite docstring):
#   descriptive  s_instrument__<src>       grain: hk           (name, ccy, sector)
#   multi-active s_instrument_price__<src> grain: hk+price_date (time series)
# Idempotent: safe to re-run.
# ============================================================

# COMMAND ----------

# MAGIC %run ./edw_lib

# COMMAND ----------

from pyspark.sql import functions as F

HUB = "ref_master.instrument.h_instrument"       # shared identity spine (ADR-5)
KM  = "ref_master.instrument.km_instrument"

# ---------- entity: instrument | source: bloomberg ----------
bb = spark.table("pubmkt_bronze.bloomberg.eod_prices")
upsert_hub_keymap(spark, bb, HUB, KM, "instrument",
                  business_key_col="isin", source_system="bloomberg", source_key_col="figi")

bb_keyed = (bb.alias("s")
    .join(spark.table(KM).where("source_system='bloomberg'").alias("k"),
          F.col("s.figi") == F.col("k.source_key"))
    .select(F.col("k.instrument_hk"),
            F.trim("s.name_full").alias("name"),
            F.upper("s.crncy").alias("currency"),
            F.col("s.industry_sector").alias("sector_raw"),
            F.col("s.px_last").alias("close_px"),
            F.col("s.price_date"),
            F.col("s._load_ts")))

# descriptive attributes -> one current row per instrument
load_satellite(spark,
    bb_keyed.select("instrument_hk", "name", "currency", "sector_raw", "price_date", "_load_ts"),
    "pubmkt_silver.instrument.s_instrument__bloomberg", "instrument",
    hash_cols=["name", "currency", "sector_raw"],
    effective_from_col="price_date", record_source="pubmkt.bloomberg.eod_prices")

# price time series -> one current row per (instrument, price_date); restatements version in place
load_satellite(spark,
    bb_keyed.select("instrument_hk", "price_date", "close_px", "_load_ts"),
    "pubmkt_silver.instrument.s_instrument_price__bloomberg", "instrument",
    hash_cols=["close_px"], subkeys=["price_date"],
    effective_from_col="price_date", record_source="pubmkt.bloomberg.eod_prices")

# ---------- entity: instrument | source: refinitiv ----------
rf = spark.table("pubmkt_bronze.refinitiv.eod_prices")
upsert_hub_keymap(spark, rf, HUB, KM, "instrument",
                  business_key_col="isin", source_system="refinitiv", source_key_col="ric")

rf_keyed = (rf.alias("s")
    .join(spark.table(KM).where("source_system='refinitiv'").alias("k"),
          F.col("s.ric") == F.col("k.source_key"))
    .select(F.col("k.instrument_hk"),
            F.initcap(F.trim("s.instr_name")).alias("name"),
            F.upper("s.ccy").alias("currency"),
            F.initcap("s.asset_cls").alias("sector_raw"),
            F.col("s.close_price").alias("close_px"),
            F.col("s.trade_date").alias("price_date"),
            F.col("s._load_ts")))

load_satellite(spark,
    rf_keyed.select("instrument_hk", "name", "currency", "sector_raw", "price_date", "_load_ts"),
    "pubmkt_silver.instrument.s_instrument__refinitiv", "instrument",
    hash_cols=["name", "currency", "sector_raw"],
    effective_from_col="price_date", record_source="pubmkt.refinitiv.eod_prices")

load_satellite(spark,
    rf_keyed.select("instrument_hk", "price_date", "close_px", "_load_ts"),
    "pubmkt_silver.instrument.s_instrument_price__refinitiv", "instrument",
    hash_cols=["close_px"], subkeys=["price_date"],
    effective_from_col="price_date", record_source="pubmkt.refinitiv.eod_prices")

# ---------- Tier-3 conformed: internal positions ----------
load_conformed(spark, "pubmkt_bronze.internal.positions",
               "pubmkt_silver.conformed.internal__positions",
               dedup_keys=["portfolio_id", "isin", "position_date"],
               order_by="_load_ts DESC")

# ---------- generated current views (precedence: bloomberg > refinitiv, entity spec) ----------
spark.sql("""
CREATE OR REPLACE VIEW pubmkt_silver.instrument.v_instrument_current AS
WITH ranked AS (
  SELECT instrument_hk, name, currency, sector_raw, record_source, 1 AS prio
  FROM pubmkt_silver.instrument.s_instrument__bloomberg WHERE is_current
  UNION ALL
  SELECT instrument_hk, name, currency, sector_raw, record_source, 2 AS prio
  FROM pubmkt_silver.instrument.s_instrument__refinitiv WHERE is_current
),
best AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY instrument_hk ORDER BY prio) AS rn FROM ranked)
SELECT h.instrument_hk, h.business_key AS isin,
       b.name, b.currency, b.sector_raw, b.record_source
FROM ref_master.instrument.h_instrument h
JOIN best b ON b.instrument_hk = h.instrument_hk AND b.rn = 1
""")

# price series view: current version of every (instrument, date), bloomberg preferred
spark.sql("""
CREATE OR REPLACE VIEW pubmkt_silver.instrument.v_instrument_price AS
WITH ranked AS (
  SELECT instrument_hk, price_date, close_px, record_source, 1 AS prio
  FROM pubmkt_silver.instrument.s_instrument_price__bloomberg WHERE is_current
  UNION ALL
  SELECT instrument_hk, price_date, close_px, record_source, 2 AS prio
  FROM pubmkt_silver.instrument.s_instrument_price__refinitiv WHERE is_current
),
best AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY instrument_hk, price_date ORDER BY prio) AS rn FROM ranked)
SELECT h.business_key AS isin, b.instrument_hk, b.price_date, b.close_px, b.record_source
FROM ref_master.instrument.h_instrument h
JOIN best b ON b.instrument_hk = h.instrument_hk AND b.rn = 1
""")

log_run(spark, "silver_pubmkt", "OK", "4 sats (2 descriptive + 2 price) + conformed + 2 views")
print("pubmkt silver loaded.")
