# Databricks notebook source
# ============================================================
# Prototype step 2: simulated source data — BATCH 1 (initial load)
# Two orgs + overlapping vendors to demonstrate hub/satellite value:
#   pubmkt: bloomberg + refinitiv EOD prices (same instruments,
#           different vendor ids, both carry ISIN), internal positions
#   pvtmkt: eFront fund valuations, DealCloud deals
# Deterministic (seeded) so runs are reproducible.
# ============================================================
from pyspark.sql import functions as F
import random, datetime

random.seed(42)
LOAD_TS = "2026-08-01T06:00:00Z"

# ---------- shared instrument universe (12 instruments) ----------
# (isin, name, currency, sector, figi, ric, base_price)
INSTRUMENTS = [
    ("SG1L01001701", "DBS Group Holdings",      "SGD", "Financials", "BBG000BFDGY6", "DBSM.SI", 35.0),
    ("SG1M31001969", "Singtel",                 "SGD", "Telecom",    "BBG000BKXVZ2", "STEL.SI",  3.1),
    ("US0378331005", "Apple Inc",               "USD", "Technology", "BBG000B9XRY4", "AAPL.OQ", 225.0),
    ("US5949181045", "Microsoft Corp",          "USD", "Technology", "BBG000BPH459", "MSFT.OQ", 445.0),
    ("US02079K3059", "Alphabet Inc A",          "USD", "Technology", "BBG009S39JX6", "GOOGL.OQ",185.0),
    ("JP3633400001", "Toyota Motor",            "JPY", "Consumer",   "BBG000BCM915", "7203.T", 2800.0),
    ("DE0007164600", "SAP SE",                  "EUR", "Technology", "BBG000BB1CX2", "SAPG.DE", 210.0),
    ("GB0005405286", "HSBC Holdings",           "GBP", "Financials", "BBG000BS1YV5", "HSBA.L",   6.9),
    ("US912828YV62", "US Treasury 10Y",         "USD", "Govt",       "BBG00R7NDFK5", "US10YT=RR",98.5),
    ("SG31A8000003", "Singapore Govt 10Y",      "SGD", "Sovereign",  "BBG00LBJZDS2", "SG10YT=RR",101.2),
    ("US037833AR12", "Apple Corp Bond 3.85%",   "USD", "Corp Bond",  "BBG006F8VWJ7", "037833AR=",99.8),
    ("XS2021455233", "Temasek 2.5% 2030",       "USD", "Corp Bond",  "BBG00PNQKF33", "XS2021455=",97.4),
]

PRICE_DATES = ["2026-07-29", "2026-07-30", "2026-07-31"]

def px(base, d_idx, jitter):
    return round(base * (1 + 0.004 * d_idx + jitter), 4)

# ---------- pubmkt_bronze.bloomberg.eod_prices ----------
bb_rows = []
for isin, name, ccy, sector, figi, ric, base in INSTRUMENTS:
    for i, d in enumerate(PRICE_DATES):
        bb_rows.append((figi, isin, name, ccy, sector,
                        px(base, i, random.uniform(-0.01, 0.01)), d, LOAD_TS))
spark.createDataFrame(
    bb_rows, "figi string, isin string, name_full string, crncy string, "
             "industry_sector string, px_last double, price_date string, _load_ts string"
).withColumn("price_date", F.col("price_date").cast("date")) \
 .withColumn("_load_ts", F.col("_load_ts").cast("timestamp")) \
 .write.mode("overwrite").saveAsTable("pubmkt_bronze.bloomberg.eod_prices")

# ---------- pubmkt_bronze.refinitiv.eod_prices ----------
# same instruments, vendor-specific ids/names/prices (small basis difference)
rf_rows = []
for isin, name, ccy, sector, figi, ric, base in INSTRUMENTS:
    for i, d in enumerate(PRICE_DATES):
        rf_rows.append((ric, isin, name.upper(), ccy, sector.upper(),
                        px(base, i, random.uniform(-0.01, 0.01)), d, LOAD_TS))
spark.createDataFrame(
    rf_rows, "ric string, isin string, instr_name string, ccy string, "
             "asset_cls string, close_price double, trade_date string, _load_ts string"
).withColumn("trade_date", F.col("trade_date").cast("date")) \
 .withColumn("_load_ts", F.col("_load_ts").cast("timestamp")) \
 .write.mode("overwrite").saveAsTable("pubmkt_bronze.refinitiv.eod_prices")

# ---------- pubmkt_bronze.internal.positions (Tier-3 → conformed) ----------
pos_rows = []
for pf in ["PF_GLOBAL_EQ", "PF_ASIA_FI"]:
    universe = INSTRUMENTS[:8] if pf == "PF_GLOBAL_EQ" else INSTRUMENTS[8:]
    for isin, *_ in [(r[0],) for r in universe]:
        pos_rows.append((pf, isin, random.randint(10_000, 500_000), "2026-07-31", LOAD_TS))
spark.createDataFrame(
    pos_rows, "portfolio_id string, isin string, qty long, position_date string, _load_ts string"
).withColumn("position_date", F.col("position_date").cast("date")) \
 .withColumn("_load_ts", F.col("_load_ts").cast("timestamp")) \
 .write.mode("overwrite").saveAsTable("pubmkt_bronze.internal.positions")

# ---------- pvtmkt_bronze.efront.fund_valuations (Tier-1 fund entity) ----------
FUNDS = [
    ("PEF-001", "Asia Growth Fund III",   2019, "USD", "PE_GR", 812.4),
    ("PEF-002", "Global Buyout Fund VII", 2021, "USD", "PE_BO", 1450.0),
    ("PEF-003", "Europe Buyout Fund II",  2018, "EUR", "PE_BO", 610.7),
    ("REF-001", "Core RE Partners I",     2020, "USD", "RE_CORE", 380.2),
]
fv_rows = [(c, n, v, ccy, ac, nav, "2026-06-30", LOAD_TS) for c, n, v, ccy, ac, nav in FUNDS]
spark.createDataFrame(
    fv_rows, "fund_code string, fund_name string, vintage int, currency string, "
             "asset_class string, nav_musd double, valuation_date string, _load_ts string"
).withColumn("valuation_date", F.col("valuation_date").cast("date")) \
 .withColumn("_load_ts", F.col("_load_ts").cast("timestamp")) \
 .write.mode("overwrite").saveAsTable("pvtmkt_bronze.efront.fund_valuations")

# ---------- pvtmkt_bronze.dealcloud.deals (Tier-3 → conformed) ----------
DEALS = [
    ("DL-1001", "Project Merlion",  "PEF-001", "Technology", "SEA fintech platform", 220.0, "SIGNED",    "2026-03-15"),
    ("DL-1002", "Project Orchid",   "PEF-002", "Healthcare", "EU medtech carve-out", 540.0, "CLOSED",    "2026-01-20"),
    ("DL-1003", "Project Kopi",     "PEF-001", "Consumer",   "Regional F&B chain",   130.0, "DILIGENCE", None),
    ("DL-1004", "Project Bayfront", "REF-001", "RealEstate", "SG logistics assets",  310.0, "CLOSED",    "2025-11-02"),
    ("DL-1005", "Project Lion",     "PEF-002", "Industrial", "Precision mfg group",  460.0, "SIGNED",    "2026-06-11"),
    ("DL-1006", "Project Coral",    "PEF-003", "Energy",     "Renewables platform",  275.0, "DILIGENCE", None),
]
dl_rows = [d + (LOAD_TS,) for d in DEALS]
spark.createDataFrame(
    dl_rows, "deal_id string, deal_name string, fund_code string, sector string, "
             "target_desc string, deal_size_musd double, status string, signed_date string, _load_ts string"
).withColumn("signed_date", F.col("signed_date").cast("date")) \
 .withColumn("_load_ts", F.col("_load_ts").cast("timestamp")) \
 .write.mode("overwrite").saveAsTable("pvtmkt_bronze.dealcloud.deals")

spark.sql("INSERT INTO edw_meta.ops.run_ledger VALUES (current_timestamp(), 'generate_batch1', 'OK', '5 bronze tables loaded')")
print("Batch 1 loaded: bloomberg(36) refinitiv(36) positions(12) fund_valuations(4) deals(6)")
