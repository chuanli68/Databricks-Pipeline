# Databricks notebook source
# ============================================================
# Prototype validation — the A6 checks (doc 03), runnable after each batch.
# Fails loudly (assert) like the real Validator gate would.
# ============================================================
from pyspark.sql import functions as F

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    spark.sql("INSERT INTO edw_meta.ops.run_ledger VALUES "
              f"(current_timestamp(), 'validate:{name}', '{status}', '{detail}')")
    assert cond, f"Validation failed: {name} {detail}"

DESCRIPTIVE = [("pubmkt_silver.instrument.s_instrument__bloomberg", "instrument_hk"),
               ("pubmkt_silver.instrument.s_instrument__refinitiv", "instrument_hk"),
               ("pvtmkt_silver.fund.s_fund__efront", "fund_hk")]
MULTIACTIVE = [("pubmkt_silver.instrument.s_instrument_price__bloomberg", ["instrument_hk", "price_date"]),
               ("pubmkt_silver.instrument.s_instrument_price__refinitiv", ["instrument_hk", "price_date"]),
               ("pvtmkt_silver.fund.s_fund_nav__efront", ["fund_hk", "valuation_date"])]

# ---------- 1. Hub / key-map integrity ----------
h = spark.table("ref_master.instrument.h_instrument")
check("hub_key_unique", h.count() == h.select("instrument_hk").distinct().count())
km = spark.table("ref_master.instrument.km_instrument")
check("keymap_unique_per_source",
      km.groupBy("source_system", "source_key").count().where("count > 1").count() == 0)

# ---------- 2. SCD2 integrity ----------
for sat, hk in DESCRIPTIVE:
    s, nm = spark.table(sat), sat.split(".")[-1]
    check(f"one_current_per_key:{nm}",
          s.where("is_current").groupBy(hk).count().where("count > 1").count() == 0)
    check(f"closed_rows_have_end:{nm}",
          s.where("NOT is_current AND effective_to IS NULL").count() == 0)

for sat, grain in MULTIACTIVE:
    s, nm = spark.table(sat), sat.split(".")[-1]
    check(f"one_current_per_grain:{nm}",
          s.where("is_current").groupBy(*grain).count().where("count > 1").count() == 0)
    check(f"closed_rows_have_end:{nm}",
          s.where("NOT is_current AND effective_to IS NULL").count() == 0)

# ---------- 3. Reconciliation: bronze -> silver ----------
bb = spark.table("pubmkt_bronze.bloomberg.eod_prices")
check("recon_bloomberg_keys",
      bb.select("figi").distinct().count() == km.where("source_system='bloomberg'").count())
# every (instrument, date) in bronze has a current price row in silver
bb_grain = bb.select("figi", "price_date").distinct().count()
px_grain = spark.table("pubmkt_silver.instrument.s_instrument_price__bloomberg") \
                .where("is_current").select("instrument_hk", "price_date").distinct().count()
check("recon_price_grain", bb_grain == px_grain, f"bronze={bb_grain} silver={px_grain}")

fv = spark.table("pvtmkt_bronze.efront.fund_valuations")
nav = spark.table("pvtmkt_silver.fund.s_fund_nav__efront")
check("recon_fund_periods",
      fv.select("fund_code", "valuation_date").distinct().count()
      == nav.where("is_current").select("fund_hk", "valuation_date").distinct().count())

# ---------- 4. Gold sanity ----------
gp = spark.table("pubmkt_gold.risk_snapshot.v_daily_position_risk")
check("gold_pubmkt_nonempty", gp.count() > 0, f"rows={gp.count()}")
check("gold_pubmkt_no_null_mv", gp.where("market_value_local IS NULL").count() == 0)
gv = spark.table("pvtmkt_gold.fund_performance.v_fund_nav_history")
check("gold_pvtmkt_nonempty", gv.count() > 0, f"rows={gv.count()}")

# ---------- 5. The stability story (informational; richest after batch 2) ----------
print("\n--- Singtel rename: SCD2 in the DESCRIPTIVE satellite (bloomberg only) ---")
spark.sql("""
  SELECT s.name, s.effective_from, s.effective_to, s.is_current
  FROM pubmkt_silver.instrument.s_instrument__bloomberg s
  JOIN ref_master.instrument.h_instrument h ON h.instrument_hk = s.instrument_hk
  WHERE h.business_key = 'SG1M31001969' ORDER BY s.effective_from""").show(truncate=False)

print("--- Same instrument in refinitiv's satellite: untouched by the rename ---")
spark.sql("""
  SELECT s.name, s.is_current FROM pubmkt_silver.instrument.s_instrument__refinitiv s
  JOIN ref_master.instrument.h_instrument h ON h.instrument_hk = s.instrument_hk
  WHERE h.business_key = 'SG1M31001969'""").show(truncate=False)

print("--- Price time series preserved per date (not collapsed) ---")
spark.sql("""
  SELECT isin, price_date, close_px FROM pubmkt_silver.instrument.v_instrument_price
  WHERE isin = 'US0378331005' ORDER BY price_date""").show()

print("--- NAV restatement: PEF-001 30-Jun has 2 versions, only that period versioned ---")
spark.sql("""
  SELECT fund_code, valuation_date, nav_musd, effective_to, is_current
  FROM pvtmkt_gold.fund_performance.v_fund_nav_history
  WHERE fund_code = 'PEF-001' ORDER BY valuation_date, effective_from""").show()

print("--- ASML: in bloomberg sat + hub, absent from refinitiv (graceful divergence) ---")
spark.sql("""
  SELECT h.business_key,
    EXISTS(SELECT 1 FROM pubmkt_silver.instrument.s_instrument__bloomberg b
           WHERE b.instrument_hk = h.instrument_hk) AS in_bloomberg,
    EXISTS(SELECT 1 FROM pubmkt_silver.instrument.s_instrument__refinitiv r
           WHERE r.instrument_hk = h.instrument_hk) AS in_refinitiv
  FROM ref_master.instrument.h_instrument h
  WHERE h.business_key = 'NL0010273215'""").show()

print("All validations passed.")
