# Step-by-Step Install & Run Guide

Target: **Databricks Free Edition**. Total time ~30–40 minutes, mostly waiting on compute.
Every step has an expected result so you know immediately if something went wrong.

---

## Step 0 — Get a workspace (5 min, skip if you have one)

1. Go to <https://www.databricks.com/learn/free-edition> and sign up (email OTP, Google, or
   Microsoft sign-in).
2. When the workspace opens you'll land on the home page with a left sidebar:
   **Workspace · Catalog · SQL Editor · Jobs & Pipelines · Compute**.
3. You are the **metastore admin** of your own account — you can create catalogs and grants,
   which is all this prototype needs.

> Free Edition is serverless-only. You never create a cluster; notebooks and SQL attach to
> serverless compute automatically. First run of the day takes ~1 min to warm up.

---

## Step 1 — Import the prototype files (3 min)

1. Left sidebar → **Workspace** → **Users** → click your email address.
2. Click the **⋮** (kebab) menu at the top right of the file list → **Import**.
3. In the dialog choose **File**, then drag in **all files from the `prototype/` folder**
   (including `edw_lib.py`). Click **Import**.
4. You should now see a folder or flat list containing:

```
00_setup_catalogs.sql      04_silver_pubmkt.py     08_access_check.sql
01_setup_grants.sql        05_silver_pvtmkt.py     09_teardown.sql
02_generate_bronze_batch1.py  06_gold.sql          edw_lib.py
03_generate_bronze_batch2.py  07_validate.py
```

**Critical:** `edw_lib.py` must sit in the **same folder** as `04_` and `05_`, because those
notebooks call `%run ./edw_lib`. If you put them in different folders, the run fails with
`Notebook not found`.

> The `.py` files carry a `# Databricks notebook source` header, so they import as **notebooks**
> (not plain files) — you can open and run them directly. The `.sql` files import as SQL
> notebooks; this guide runs them in the SQL Editor instead, which handles multi-statement
> scripts more reliably.

---

## Step 2 — Create catalogs and shared reference data (2 min)

1. Left sidebar → **SQL Editor** → **New query**.
2. Open `00_setup_catalogs.sql` from your workspace, copy its entire contents, paste into the
   editor.
3. Click the **▾ next to Run** → **Run all** (not just "Run selected"). If your warehouse is
   stopped it auto-starts — wait ~1 min.

**Expected:** final result `setup complete`.

**Verify** — left sidebar → **Catalog**, click refresh. You should see 8 new catalogs:

```
edw_meta  pubmkt_bronze  pubmkt_gold  pubmkt_silver
ref_master  pvtmkt_bronze  pvtmkt_gold  pvtmkt_silver
```

Expand `ref_master` → `reference` → you should see `asset_class` (7 rows) and `currency` (5 rows).

---

## Step 3 — Grants (optional, 2 min)

Skip this if you're running single-user; do it if you want the isolation demo (Step 10).

1. Open `01_setup_grants.sql`, replace the two placeholder emails with real ones.
2. Run all in the SQL Editor.

**Expected:** no errors. If you see `PRINCIPAL_DOES_NOT_EXIST`, the user isn't in your workspace
yet — add them first: **Settings** (gear, top right) → **Identity and access** → **Users** →
**Add user**.

---

## Step 4 — Load simulated source data, batch 1 (3 min)

1. **Workspace** → open `02_generate_bronze_batch1.py`.
2. Top right: confirm compute shows **Serverless** (it attaches automatically).
3. **Run all** (or `Ctrl/Cmd + Shift + Enter`).

**Expected output:**

```
Batch 1 loaded: bloomberg(36) refinitiv(36) positions(12) fund_valuations(4) deals(6)
```

**Verify** in SQL Editor:

```sql
SELECT count(*) FROM pubmkt_bronze.bloomberg.eod_prices;   -- 36
SELECT count(*) FROM pvtmkt_bronze.efront.fund_valuations; -- 4
```

---

## Step 5 — Build public-markets silver (3 min)

1. Open `04_silver_pubmkt.py` → **Run all**.
2. The first cell is `%run ./edw_lib`, which loads the loading-pattern functions.

**Expected output:** `pubmkt silver loaded.`

**Verify — these are the numbers that matter:**

```sql
SELECT count(*) FROM ref_master.instrument.h_instrument;                       -- 12  (one per ISIN)
SELECT count(*) FROM ref_master.instrument.km_instrument;                      -- 24  (12 x 2 vendors)
SELECT count(*) FROM pubmkt_silver.instrument.s_instrument__bloomberg;         -- 12  descriptive: 1/instrument
SELECT count(*) FROM pubmkt_silver.instrument.s_instrument_price__bloomberg;   -- 36  multi-active: 12 x 3 dates
SELECT count(*) FROM pubmkt_silver.conformed.internal__positions;              -- 12
```

The contrast between **12** and **36** is the whole point of the two satellite kinds: descriptive
attributes collapse to one current row per instrument; the price series keeps every date.

---

## Step 6 — Build private-markets silver (2 min)

Open `05_silver_pvtmkt.py` → **Run all**. **Expected:** `pvtmkt silver loaded.`

```sql
SELECT count(*) FROM pvtmkt_silver.fund.h_fund;             -- 4
SELECT count(*) FROM pvtmkt_silver.fund.s_fund__efront;     -- 4  descriptive
SELECT count(*) FROM pvtmkt_silver.fund.s_fund_nav__efront; -- 4  one NAV period so far
SELECT count(*) FROM pvtmkt_silver.conformed.dealcloud__deals; -- 6
```

---

## Step 7 — Create gold views (2 min)

SQL Editor → paste `06_gold.sql` → **Run all**. **Expected:** `gold views created`.

```sql
SELECT * FROM pubmkt_gold.risk_snapshot.v_daily_position_risk ORDER BY isin;   -- 12 rows
SELECT * FROM pvtmkt_gold.fund_performance.v_fund_nav_history;                 --  4 rows
SELECT * FROM pvtmkt_gold.fund_performance.v_deal_pipeline;                    --  6 rows
```

Both gold views join `ref_master.reference.asset_class` — the shared dataset each org can read.

---

## Step 8 — Validate (2 min)

Open `07_validate.py` → **Run all**.

**Expected:** every line prefixed `[PASS]`, ending with `All validations passed.`
Any `[FAIL]` raises an `AssertionError` and stops — the message names the failed check.

---

## Step 9 — The change demo (5 min) — *this is the point of the prototype*

1. Open `03_generate_bronze_batch2.py` → **Run all**.
   Expected: `Batch 2 loaded. Re-run silver pipelines...`
2. Re-run `04_silver_pubmkt.py` → **Run all**.
3. Re-run `05_silver_pvtmkt.py` → **Run all**.
4. Re-run `07_validate.py` → **Run all**. All `[PASS]` again, and the printouts at the end now
   tell the story.

**What changed, and what didn't:**

```sql
-- 1. Singtel renamed -> SCD2 version in ONE satellite (12 -> 14 rows: +1 rename, +1 ASML)
SELECT s.name, s.effective_from, s.effective_to, s.is_current
FROM pubmkt_silver.instrument.s_instrument__bloomberg s
JOIN ref_master.instrument.h_instrument h ON h.instrument_hk = s.instrument_hk
WHERE h.business_key = 'SG1M31001969' ORDER BY s.effective_from;
-- 2 rows: old name closed, new name current

-- 2. The other vendor's satellite: untouched, still 12 rows
SELECT count(*) FROM pubmkt_silver.instrument.s_instrument__refinitiv;         -- 12

-- 3. Price history appended, not rebuilt
SELECT count(*) FROM pubmkt_silver.instrument.s_instrument_price__bloomberg;   -- 49 (36 + 13)

-- 4. NAV RESTATEMENT: PEF-001's 30-Jun mark corrected 812.4 -> 798.6
SELECT valuation_date, nav_musd, effective_to, is_current
FROM pvtmkt_gold.fund_performance.v_fund_nav_history
WHERE fund_code = 'PEF-001' ORDER BY valuation_date, effective_from;
-- 30-Jun appears TWICE (812.4 closed, 798.6 current); 31-Jul unaffected

-- 5. Nothing else moved: other funds still single-version
SELECT count(*) FROM pvtmkt_silver.fund.s_fund_nav__efront;                    -- 9
```

Expected counts after batch 2:

| Table | Before | After | Why |
|---|---|---|---|
| `h_instrument` | 12 | 13 | ASML added |
| `s_instrument__bloomberg` | 12 | 14 | +1 rename version, +1 ASML |
| `s_instrument__refinitiv` | 12 | 12 | **untouched by the rename** |
| `s_instrument_price__bloomberg` | 36 | 49 | new date appended |
| `s_fund__efront` | 4 | 4 | descriptive attrs unchanged |
| `s_fund_nav__efront` | 4 | 9 | +4 new period, +1 restatement version |
| gold views | valid | valid | **no DDL change, no reload** |

No table was dropped or rebuilt at any point. That is the stability guarantee, demonstrated.

---

## Step 10 — Prove the org isolation (optional, 5 min)

**Single-user check** — SQL Editor, run each and read the grantees:

```sql
SHOW GRANTS ON CATALOG pubmkt_gold;     -- pubmkt analyst only
SHOW GRANTS ON CATALOG pvtmkt_gold;     -- pvtmkt analyst only
SHOW GRANTS ON SCHEMA  ref_master.reference;  -- BOTH analysts
SHOW GRANTS ON CATALOG pubmkt_bronze;   -- no analyst grants at all
```

**Two-user check (the real demo)** — have the pubmkt analyst sign in and run:

```sql
SELECT * FROM pubmkt_gold.risk_snapshot.v_daily_position_risk LIMIT 5;  -- works
SELECT * FROM ref_master.reference.asset_class;                          -- works (shared)
SELECT * FROM pvtmkt_gold.fund_performance.v_fund_nav_history LIMIT 5;   -- PERMISSION_DENIED
SHOW CATALOGS;                        -- pvtmkt_* do not even appear
```

Invisible, not merely unqueryable — that's the information barrier.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Notebook not found: ./edw_lib` | `edw_lib.py` isn't beside `04_`/`05_` | Move it into the same folder |
| `NameError: name 'load_satellite' is not defined` | The `%run` cell didn't execute | Run the notebook from the top (**Run all**), not just one cell |
| `Table or view not found` in step 5 | Step 4 wasn't run, or ran in a different workspace | Re-run `02_generate_bronze_batch1.py` |
| `PERMISSION_DENIED` creating catalogs | You're not metastore admin | On Free Edition you are by default; confirm you're in your own account |
| `PRINCIPAL_DOES_NOT_EXIST` on grants | User not added to workspace | Settings → Identity and access → Users → Add user |
| SQL Editor runs only the first statement | Used "Run" instead of "Run all" | Use the **▾ → Run all** |
| Compute won't start / quota message | Free Edition daily quota hit | Wait for the daily reset; quotas are per-account |
| Validation `[FAIL] recon_price_grain` | Silver re-run skipped after loading batch 2 | Re-run steps 5 and 6, then validate |

---

## Reset / cleanup

- **Start completely fresh:** run `09_teardown.sql` (drops all 8 catalogs), then begin at Step 2.
- **Re-run anything safely:** every pipeline notebook is idempotent — running `04_`/`05_` twice
  produces no duplicate SCD2 versions. Verified by test.
- **Just re-do the change demo:** teardown → steps 2, 4, 5, 6, 7, then 9.

---

## What to read next

- `README.md` (this folder) — what each artifact demonstrates and how it maps to the design.
- `specs/` — the contract, mapping, entity, and use-case files that (in the real system) the
  agents would produce and from which this pipeline code would be generated.
- `../docs/06-silver-standards-codegen.md` — the physical standards these pipelines implement,
  including §1.3b on descriptive vs multi-active satellites.
