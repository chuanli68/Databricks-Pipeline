# Databricks notebook source
# ============================================================
# Prototype step 3 (run AFTER first silver run): BATCH 2 — the change demo
# Demonstrates the stability guarantees:
#   1. New price date (normal increment)
#   2. Bloomberg renames an instrument       -> SCD2 new version in ONE satellite
#   3. A new instrument appears              -> new hub row, no reshape
#   4. eFront restates a fund NAV            -> SCD2 in fund satellite
#   5. A deal changes status + a new deal    -> conformed table refresh
# Nothing here touches refinitiv's satellite, links, or gold view DDL.
# ============================================================
from pyspark.sql import functions as F
import random

random.seed(43)
LOAD_TS = "2026-08-02T06:00:00Z"
NEW_DATE = "2026-08-01"

# 1+2+3: bloomberg batch — new date, one rename, one new instrument
bb = spark.table("pubmkt_bronze.bloomberg.eod_prices") \
          .where("price_date = '2026-07-31'") \
          .withColumn("price_date", F.lit(NEW_DATE).cast("date")) \
          .withColumn("px_last", F.round(F.col("px_last") * (1 + (F.rand(7) - 0.5) / 50), 4)) \
          .withColumn("_load_ts", F.lit(LOAD_TS).cast("timestamp")) \
          .withColumn("name_full",
              F.when(F.col("isin") == "SG1M31001969", F.lit("Singapore Telecommunications Ltd"))  # rename!
               .otherwise(F.col("name_full")))
new_instr = spark.createDataFrame(
    [("BBG000C6K6G9", "NL0010273215", "ASML Holding", "EUR", "Technology", 890.5, NEW_DATE, LOAD_TS)],
    "figi string, isin string, name_full string, crncy string, industry_sector string, "
    "px_last double, price_date string, _load_ts string"
).withColumn("price_date", F.col("price_date").cast("date")) \
 .withColumn("_load_ts", F.col("_load_ts").cast("timestamp"))
bb.unionByName(new_instr).write.mode("append").saveAsTable("pubmkt_bronze.bloomberg.eod_prices")

# refinitiv: new date only, still 12 instruments (does NOT have ASML yet —
# demonstrates per-source satellites diverging gracefully)
rf = spark.table("pubmkt_bronze.refinitiv.eod_prices") \
          .where("trade_date = '2026-07-31'") \
          .withColumn("trade_date", F.lit(NEW_DATE).cast("date")) \
          .withColumn("close_price", F.round(F.col("close_price") * (1 + (F.rand(11) - 0.5) / 50), 4)) \
          .withColumn("_load_ts", F.lit(LOAD_TS).cast("timestamp"))
rf.write.mode("append").saveAsTable("pubmkt_bronze.refinitiv.eod_prices")

# positions: new snapshot date
pos = spark.table("pubmkt_bronze.internal.positions") \
           .withColumn("position_date", F.lit(NEW_DATE).cast("date")) \
           .withColumn("qty", (F.col("qty") * (1 + (F.rand(13) - 0.5) / 10)).cast("long")) \
           .withColumn("_load_ts", F.lit(LOAD_TS).cast("timestamp"))
pos.write.mode("append").saveAsTable("pubmkt_bronze.internal.positions")

# 4a: eFront Q3 marks — new valuation period for all funds
fv = spark.table("pvtmkt_bronze.efront.fund_valuations") \
          .where("valuation_date = '2026-06-30'") \
          .withColumn("valuation_date", F.lit("2026-07-31").cast("date")) \
          .withColumn("nav_musd", F.round(F.col("nav_musd") * (1 + (F.rand(17) - 0.4) / 20), 1)) \
          .withColumn("_load_ts", F.lit(LOAD_TS).cast("timestamp"))
fv.write.mode("append").saveAsTable("pvtmkt_bronze.efront.fund_valuations")

# 4b: RESTATEMENT — PEF-001's 30-Jun NAV is corrected after audit.
# Same valuation_date, new value: the multi-active satellite versions ONLY that
# period, preserving what was reported before. Other funds/periods untouched.
restate = spark.table("pvtmkt_bronze.efront.fund_valuations") \
               .where("fund_code = 'PEF-001' AND valuation_date = '2026-06-30'") \
               .limit(1) \
               .withColumn("nav_musd", F.lit(798.6)) \
               .withColumn("_load_ts", F.lit(LOAD_TS).cast("timestamp"))
restate.write.mode("append").saveAsTable("pvtmkt_bronze.efront.fund_valuations")

# 5: deal status change + new deal
spark.createDataFrame(
    [("DL-1003", "Project Kopi", "PEF-001", "Consumer", "Regional F&B chain", 135.0, "SIGNED", "2026-07-28", LOAD_TS),
     ("DL-1007", "Project Marina", "PEF-003", "Technology", "Nordic SaaS roll-up", 190.0, "DILIGENCE", None, LOAD_TS)],
    "deal_id string, deal_name string, fund_code string, sector string, target_desc string, "
    "deal_size_musd double, status string, signed_date string, _load_ts string"
).withColumn("signed_date", F.col("signed_date").cast("date")) \
 .withColumn("_load_ts", F.col("_load_ts").cast("timestamp")) \
 .write.mode("append").saveAsTable("pvtmkt_bronze.dealcloud.deals")

spark.sql("INSERT INTO edw_meta.ops.run_ledger VALUES (current_timestamp(), 'generate_batch2', 'OK', 'change-demo batch loaded')")
print("Batch 2 loaded. Re-run silver pipelines, then check SCD2 history (see 06_validate).")
