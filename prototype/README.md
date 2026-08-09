# Prototype — Overview (Databricks Free Edition)

> **Installing?** Follow [INSTALL.md](INSTALL.md) — step-by-step with expected results,
> verification queries, and troubleshooting. This file explains *what* the prototype proves.

A working miniature of the design: two orgs (public markets, private markets) with isolated
catalogs, shared reference data both can read, bronze → silver (hub/link/satellite) → gold,
and a second data batch that proves the stability guarantees.

## What it demonstrates

| Design claim | Where you see it |
|---|---|
| Org isolation by Unity Catalog grants | `01_setup_grants.sql`, `08_access_check.sql` |
| Shared reference data readable by both orgs | `ref_master.reference.*` joined in both gold views |
| Shared identity spine, not shared org data | `ref_master.instrument.h_instrument` (runtime only, not granted to analysts) |
| Silver stable under source change | Batch 2: rename + new instrument → **1 satellite touched, zero reloads** |
| SCD2 for free | `s_instrument__bloomberg`, `s_fund__efront` history in `07_validate.py` |
| Multi-active satellites (doc 06 §1.3b) | `s_instrument_price__*` (per date), `s_fund_nav__efront` (per period) |
| Restatement handling | Batch 2 corrects PEF-001's 30-Jun NAV → **only that period versions**; other periods and funds untouched |
| Per-source satellites diverge gracefully | ASML lands in bloomberg sat only; refinitiv sat unaffected |
| Tier-3 conformed silver (bronze stays raw) | `pubmkt_silver.conformed.*`, `pvtmkt_silver.conformed.*` |
| Specs generate code | `specs/` → the "generated-style" pipeline files |

## Free Edition constraints (verified Aug 2026)

Serverless only; **one active pipeline per pipeline type**, so the prototype uses plain notebooks
rather than DLT (the same logic; DLT expectations are noted in comments). One workspace/metastore,
**no account console**, so grants target individual users, not account groups. No SSO/SCIM.
Catalog creation and `GRANT` work normally — the isolation demo is real.

## Run order

| # | File | Run as | Notes |
|---|---|---|---|
| 0 | `00_setup_catalogs.sql` | SQL editor | Creates 8 catalogs + schemas + seeds shared reference data |
| 1 | `01_setup_grants.sql` | SQL editor | **Edit the two emails first.** Optional if running single-user |
| 2 | `02_generate_bronze_batch1.py` | Notebook | Loads 5 bronze tables (simulated sources) |
| 3 | `edw_lib.py` | — | Import only; keep in the same folder as the silver notebooks |
| 4 | `04_silver_pubmkt.py` | Notebook | Hub/km + 4 satellites (2 descriptive, 2 price) + conformed + 2 views |
| 5 | `05_silver_pvtmkt.py` | Notebook | Fund hub/km + descriptive sat + NAV sat + conformed deals + view |
| 6 | `06_gold.sql` | SQL editor | 4 gold views across both orgs |
| 7 | `07_validate.py` | Notebook | A6-style checks; asserts on failure |
| 8 | `03_generate_bronze_batch2.py` | Notebook | **The change demo** |
| 9 | Re-run 4, 5, then 7 | | Observe: SCD2 versions appear, nothing else changes |
| 10 | `08_access_check.sql` | SQL editor | Grant inspection + barrier audit |
| — | `09_teardown.sql` | SQL editor | Drops all 8 catalogs to start clean |

Setup note: `%run ./edw_lib` requires `edw_lib.py` to sit in the same workspace folder as
`04_`/`05_`. Import the whole `prototype/` folder into Databricks (Workspace → Import → File,
or clone via Git folder) to keep the relative path working.

## What to look for after step 9

1. **Singtel renamed** — `s_instrument__bloomberg` now has 2 rows for that instrument: the old
   name closed (`effective_to` set, `is_current=false`), new name current. Refinitiv's satellite
   still has 1 row. No table was rebuilt.
2. **ASML added** — one new hub row, one new bloomberg satellite row. The refinitiv satellite,
   the positions table, and both gold views are untouched and still valid.
3. **Fund NAV restated** — PEF-001's 30-Jun NAV is corrected from 812.4 to 798.6.
   `v_fund_nav_history` shows **both values for the same valuation date**: the original closed
   (`is_current=false`, `effective_to` set), the correction current. The 31-Jul period and every
   other fund are untouched. This is the audit trail a NAV restatement needs, and it only works
   because NAV lives in a multi-active satellite keyed by `(fund_hk, valuation_date)`.
4. **Deal status change** — `DL-1003` flips DILIGENCE → SIGNED in the conformed table
   (recomputed from bronze, which retains both records as the replay log).

## Verifying isolation properly

Single-user (you are metastore admin, so you see everything): run `08_access_check.sql` part A/B
— it inspects *grants* rather than your own visibility.

Two-user (the real demo): invite a second account under Settings → Identity and access → Users,
put their email in `01_setup_grants.sql` as the pvtmkt analyst, then have them run part C.
`pubmkt_gold` and `ref_master.reference` succeed; `pvtmkt_gold` fails and doesn't even appear in
`SHOW CATALOGS`.

## Mapping prototype → production design

The prototype hand-renders what the agent factory would generate. `specs/` holds the real
inputs — contracts, mappings, entity specs, use cases — and `edw_lib.py` holds the loading
patterns that `templates/satellite_merge.sql.j2` renders per mapping. To extend: add a source by
writing a contract + mapping, then a matching block in the silver notebook. In production A1–A6
do that and open the PR; here you do it by hand to see the shape.

Deliberate simplifications: notebooks instead of DLT (Free Edition pipeline limit); user grants
instead of groups/service principals (no account console); ISIN as the instrument business key
(production uses an enterprise instrument id with composite fallback); asset-class mapping done in the
gold view rather than a mapping `custom_transform`; no links table (single-entity domains).

## Testing note

The loading patterns in `edw_lib.py` were verified before delivery: SCD2 semantics
(idempotent reload, close-on-change, new-key insert, value-reverts-to-old-value, one-current-per-
grain) and a full two-batch bronze→silver→gold simulation, all asserted. Two bugs were found and
fixed that way — a `SELECT * EXCEPT` that parses on Databricks but not OSS Spark, and the
missing multi-active satellite pattern that would have silently collapsed price history.
The Databricks-specific parts (Unity Catalog DDL, `MERGE INTO` on Delta, grants) could not be
executed in that environment and are the parts to watch on your first run.
