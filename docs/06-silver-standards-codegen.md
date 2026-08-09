# 06 — Silver Physical Standards and Codegen

These standards are what make codegen possible: every table type has exactly one shape and one
loading pattern, so A4 is template-filling, not programming.

## 1. Physical standards

### 1.1 Hub

```sql
CREATE TABLE h_instrument (
  instrument_hk   STRING NOT NULL,   -- sha2(upper(trim(business_key)), 256)
  business_key    STRING NOT NULL,   -- e.g. enterprise instrument id, or composite '||'-joined
  first_seen_at   TIMESTAMP,
  first_seen_src  STRING
) -- PK (instrument_hk); insert-only; NEVER altered
```

### 1.2 Key map (per entity)

```sql
CREATE TABLE km_instrument (
  instrument_hk  STRING NOT NULL,
  source_system  STRING NOT NULL,   -- 'bloomberg'
  source_key     STRING NOT NULL,   -- vendor id (FIGI, RIC, …)
  valid_from     TIMESTAMP, valid_to TIMESTAMP
) -- resolves N source ids → 1 identity; the generalized security-master pattern
```

### 1.3 Satellite (per entity × source) — SCD2 by construction

```sql
CREATE TABLE s_instrument__bloomberg (
  instrument_hk   STRING NOT NULL,
  load_ts         TIMESTAMP NOT NULL,
  effective_from  TIMESTAMP NOT NULL,
  effective_to    TIMESTAMP,          -- NULL = current
  is_current      BOOLEAN,
  hash_diff       STRING NOT NULL,    -- sha2 over all payload cols, canonical order/format
  record_source   STRING,
  -- payload columns from mapping.yml …
  name STRING, asset_class STRING, currency STRING, …
)
```

Rules: `hash_diff` is computed over the column list declared in the mapping, in canonical order
and canonical formatting. Additive columns change hash inputs, so the mapping versions its hash
column list; the first load after an additive change simply opens a new SCD2 version for rows
whose new column is non-null — correct behavior, no reload.
Timezone: all timestamps UTC; `effective_from` = source event time when the contract declares
one, else `load_ts`.

### 1.3b Multi-active satellite (time series / periodic data)

A descriptive satellite holds **one current row per hub key** — correct for attributes that
describe the entity (name, currency, sector). It is *wrong* for data that is inherently a series:
daily prices, quarterly NAVs, periodic ratings. Loading a multi-date batch into a descriptive
satellite silently keeps only the latest row per key.

For those, add the period column(s) to the grain — a **multi-active satellite**:

```sql
CREATE TABLE s_instrument_price__bloomberg (
  instrument_hk  STRING NOT NULL,
  price_date     DATE   NOT NULL,   -- sub-key: part of the grain
  load_ts        TIMESTAMP, effective_from TIMESTAMP, effective_to TIMESTAMP,
  is_current     BOOLEAN, hash_diff STRING, record_source STRING,
  close_px       DECIMAL(18,6)
) -- grain: (instrument_hk, price_date); SCD2 applies WITHIN each period
```

Same MERGE pattern, matching on `hk + sub-keys` instead of `hk` alone. The payoff is restatement
handling: when a vendor corrects one period's value, only that period gets a new SCD2 version;
all other periods, other sources, and the hub are untouched. That is the audit trail a NAV
restatement or a corrected price requires, and it is not achievable with a descriptive satellite.

Rule for the Modeler/A3: an attribute belongs in a multi-active satellite if the source can
legitimately supply **more than one value for the same entity at the same time**, distinguished
by a period or category key. The mapping declares this with `subkeys:` (see `templates/mapping.yml`);
picking the wrong satellite kind is a modeling error the Validator (A6) catches via the
`recon_*_grain` check — bronze distinct (key, period) count must equal silver current-row count.

### 1.4 Link, current view, conformed silver

- Link: hub-key pairs + `load_ts`, insert-only.
- `v_<entity>_current`: generated view joining hub + `is_current` slices of the org's preferred
  satellites with a documented source-precedence rule per attribute (from entity spec). Gold
  reads only these and the sats it explicitly needs for history.
- Conformed silver (Tier 3): lives in `<org>_silver.conformed`; typed, renamed to `snake_case`,
  deduped on declared grain, quarantine table for expectation failures. Source-shaped otherwise.
  Bronze is never conformed: it stays raw as-landed, so it can serve as the replay log (§5).

## 2. Loading pattern (one per table type, rendered by Jinja)

Satellite load (the workhorse — thousands of instances of this one pattern):

```
staged = clean(bronze source)                      -- type casts, renames from mapping
keyed  = staged JOIN km (resolve/insert identity)  -- new source keys → hub+km upsert first
hashed = add hash_diff
MERGE INTO satellite USING hashed
  ON hk match AND is_current AND hash_diff equal   → do nothing (no change)
  ON hk match AND is_current AND hash_diff differs → close old row (effective_to, is_current=false),
                                                     insert new current row
  ON no match                                      → insert new current row
```

DLT expectations rendered from contract `checks`:
`EXPECT (close_px > 0) ON VIOLATION DROP ROW` (dropped rows → quarantine + DQ event for Sentinel).

## 3. Codegen template inventory (`edw-agent-factory/templates/`)

| Template | Renders | Per |
|---|---|---|
| `bronze_ingest.py.j2` | Auto Loader / Lakeflow Connect ingestion | source feed |
| `hub_keymap_upsert.sql.j2` | Hub + key-map governed upsert | entity × source |
| `satellite_merge.sql.j2` | §2 pattern (see [templates/satellite_merge.sql.j2](../templates/satellite_merge.sql.j2)) | entity × source |
| `link_load.sql.j2` | Link insert | relationship × source |
| `conformed.sql.j2` | Tier-3 conformed silver | table |
| `current_view.sql.j2` | Precedence-merged current view | entity |
| `gold_view.sql.j2` | Use-case projection | view |
| `expectations.j2` | DLT expectations block | table |
| `test_pipeline.py.j2` | pytest unit tests + synthetic fixtures | pipeline |

Rendering is deterministic; templates are versioned; a template fix can be re-rendered across all
existing mappings (`regen --all --template satellite_merge`) producing a reviewable mass PR —
this is how you upgrade thousands of pipelines uniformly, and it is the payoff of ADR-2.

## 4. Schema evolution decision table (enforced by A7 + CI)

| Source change | Automated action | Reload? |
|---|---|---|
| Column added | Minor bump; `mergeSchema` adds to satellite; mapping updated | No |
| Type widened | Minor bump; evolve column | No |
| Column dropped | Major; column retained in sat, marked deprecated, stops populating | No |
| Column renamed | Major; treated as drop+add unless steward confirms rename (then mapping alias, hash preserved) | No |
| Type narrowed / semantic change | Major; new satellite `_v2`, old frozen queryable | Backfill new sat only |
| Grain/key change | Major, human-led (R6); new source generation | New sat lineage only |
| Vendor replaced | New satellite + km entries; old sat frozen | No |

Invariant: **no change class touches hubs, links, other satellites, or gold view contracts.**
Gold views referencing a deprecated column fail fast in CI at regen time — caught at build, not
at query time.

## 5. Backfill and reload policy

- Unit of reload = one satellite. Rebuild = re-run its mapping over bronze history (bronze is the
  immutable replay log — bronze retention policy must support this; default: keep raw forever in
  cheap storage).
- Backfills run as parameterized runs of the same generated code (`--from-date`), writing to a
  shadow table, validated by A6's reconciliation checks, then atomically swapped (R4).
