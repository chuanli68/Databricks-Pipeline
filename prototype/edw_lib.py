# Databricks notebook source
# ============================================================
# edw_lib — the deterministic loading patterns of doc 06, as reusable
# functions. In production these bodies are what the Jinja templates
# render per table; the prototype shares them as a library for brevity.
# Idempotent: re-running a batch produces no duplicate SCD2 versions.
# ============================================================
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def _sql(spark, q):
    return spark.sql(q)


def ensure_hub(spark, hub_table, km_table, entity):
    _sql(spark, f"""
      CREATE TABLE IF NOT EXISTS {hub_table} (
        {entity}_hk STRING NOT NULL, business_key STRING NOT NULL,
        first_seen_at TIMESTAMP, first_seen_src STRING)""")
    _sql(spark, f"""
      CREATE TABLE IF NOT EXISTS {km_table} (
        {entity}_hk STRING NOT NULL, source_system STRING NOT NULL,
        source_key STRING NOT NULL, valid_from TIMESTAMP)""")


def upsert_hub_keymap(spark, staged_df, hub_table, km_table, entity,
                      business_key_col, source_system, source_key_col):
    """Hub + key-map governed upsert (doc 06 §1.1/1.2). Insert-only; never reshapes."""
    ensure_hub(spark, hub_table, km_table, entity)
    keys = (staged_df
            .select(F.upper(F.trim(F.col(business_key_col))).alias("business_key"),
                    F.col(source_key_col).alias("source_key"))
            .dropDuplicates(["business_key", "source_key"])
            .withColumn(f"{entity}_hk", F.sha2(F.col("business_key"), 256)))
    keys.createOrReplaceTempView("v_keys")
    _sql(spark, f"""
      MERGE INTO {hub_table} h
      USING (SELECT DISTINCT {entity}_hk, business_key FROM v_keys) s
      ON h.{entity}_hk = s.{entity}_hk
      WHEN NOT MATCHED THEN INSERT ({entity}_hk, business_key, first_seen_at, first_seen_src)
        VALUES (s.{entity}_hk, s.business_key, current_timestamp(), '{source_system}')""")
    _sql(spark, f"""
      MERGE INTO {km_table} k
      USING v_keys s
      ON k.{entity}_hk = s.{entity}_hk AND k.source_system = '{source_system}'
         AND k.source_key = s.source_key
      WHEN NOT MATCHED THEN INSERT ({entity}_hk, source_system, source_key, valid_from)
        VALUES (s.{entity}_hk, '{source_system}', s.source_key, current_timestamp())""")


def load_satellite(spark, staged_df, sat_table, entity, hash_cols,
                   effective_from_col, record_source, subkeys=None,
                   arrival_col="_load_ts"):
    """SCD2 satellite MERGE (doc 06 §2): close-on-change, insert-new, no-op on same hash.
    staged_df must contain <entity>_hk + payload columns + effective_from_col.

    subkeys=None  -> descriptive satellite: one current row per hub key.
                     Use for attributes that describe the entity (name, currency, sector).
    subkeys=[...] -> multi-active satellite: one current row per (hub key + subkeys),
                     e.g. subkeys=['price_date'] for a price time series or
                     ['valuation_date'] for NAV. Each period is its own SCD2 track, so a
                     restatement of one period versions only that period.
    Choosing the wrong one is a real modeling error: a descriptive satellite fed a
    multi-date batch keeps only the latest row per key (correct for 'current state',
    wrong for time series)."""
    hk = f"{entity}_hk"
    grain = [hk] + list(subkeys or [])
    staged = (staged_df
              .withColumn("hash_diff", F.sha2(F.concat_ws("||",
                  *[F.coalesce(F.col(c).cast("string"), F.lit(" ")) for c in hash_cols]), 256))
              .withColumn("effective_from", F.col(effective_from_col).cast("timestamp"))
              .withColumn("record_source", F.lit(record_source)))
    # Keep the latest arrival per grain key within the batch.
    # Tiebreaker matters: a restatement carries the SAME effective date as the row it
    # corrects, so ordering by effective_from alone is ambiguous and would sometimes
    # keep the stale value. arrival_col (ingest timestamp) breaks the tie.
    order_by = [F.col("effective_from").desc()]
    if arrival_col and arrival_col in staged.columns:
        order_by.append(F.col(arrival_col).desc())
    staged = (staged.withColumn("_rn", F.row_number().over(
                  Window.partitionBy(*grain).orderBy(*order_by)))
              .where("_rn = 1").drop("_rn"))

    payload_cols = [c for c in staged.columns]
    if not spark.catalog.tableExists(sat_table):
        empty = staged.limit(0) \
            .withColumn("effective_to", F.lit(None).cast("timestamp")) \
            .withColumn("is_current", F.lit(True))
        empty.write.saveAsTable(sat_table)

    staged.createOrReplaceTempView("v_staged")
    grain_match = " AND ".join(f"t.{c} = s.{c}" for c in grain)
    # step 1: close changed current rows
    _sql(spark, f"""
      MERGE INTO {sat_table} t
      USING v_staged s
      ON {grain_match} AND t.is_current = true
      WHEN MATCHED AND t.hash_diff <> s.hash_diff
        THEN UPDATE SET t.is_current = false, t.effective_to = s.effective_from""")
    # step 2: insert rows that have no identical current version
    cols = ", ".join(payload_cols)
    scols = ", ".join(f"s.{c}" for c in payload_cols)
    _sql(spark, f"""
      INSERT INTO {sat_table} ({cols}, effective_to, is_current)
      SELECT {scols}, CAST(NULL AS TIMESTAMP), true
      FROM v_staged s
      WHERE NOT EXISTS (SELECT 1 FROM {sat_table} t
                        WHERE {grain_match} AND t.is_current = true
                          AND t.hash_diff = s.hash_diff)""")


def load_conformed(spark, source_table, target_table, dedup_keys, order_by,
                   renames=None, casts=None):
    """Tier-3 conformed silver (doc 06 §1.4): typed, renamed, deduped; source-shaped.
    Deterministic recompute from bronze (bronze is the replay log)."""
    df = spark.table(source_table)
    for old, new in (renames or {}).items():
        df = df.withColumnRenamed(old, new)
    for c, t in (casts or {}).items():
        df = df.withColumn(c, F.col(c).cast(t))
    order_expr = [F.expr(o) for o in (order_by.split(",") if isinstance(order_by, str) else order_by)]
    deduped = (df.withColumn("_rn", F.row_number().over(
                   Window.partitionBy(*dedup_keys).orderBy(*order_expr)))
                 .where("_rn = 1").drop("_rn"))
    deduped.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(target_table)


def log_run(spark, component, status, detail):
    spark.sql("INSERT INTO edw_meta.ops.run_ledger VALUES "
              f"(current_timestamp(), '{component}', '{status}', '{detail}')")
