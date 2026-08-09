# 05 — Unity Catalog Design and Access Control

Single metastore, deployed in the primary operating region. Workspaces may be shared or per-org;
isolation comes from UC grants, not workspace boundaries.

## 1. Catalog matrix

| Catalog | Purpose | Notes |
|---|---|---|
| `<org>_bronze` | Raw only, as-landed — no typing, cleaning, or dedup | orgs: `pubmkt`, `pvtmkt`, `pe`, … Schema per source system |
| `<org>_silver` | Canonical core + conformed | See §2 |
| `<org>_gold` | Use-case projections | Schema per use case / consumer group |
| `<org>_dev`, `<org>_test` | Sandbox / CI | Wiped on schedule |
| `ref_master` | Cross-org hubs + key maps (instrument, party) + reference data | The only cross-org data surface |
| `edw_meta` | State, audit, DQ events, profiling results | Platform-owned |

## 2. Schema layout inside `<org>_silver`

```
<org>_silver
├── instrument/           # subject-area schemas (Tier 1)
│     h_instrument                # hub: only if org-specific; shared hubs live in ref_master
│     l_instrument_issuer        # links
│     s_instrument__bloomberg    # satellite per source
│     s_instrument__refinitiv
│     v_instrument_current       # generated current-view (consumers of silver, i.e. gold, use these)
├── position/ …
├── transaction/ …
└── conformed/            # Tier 3 long tail
      <source_system>__<table>   # cleaned, typed, deduped, source-shaped
```

Naming: `h_` hub, `l_` link, `s_<entity>__<source>` satellite, `v_<entity>_current` current view,
`km_<entity>` key map. Versioned satellites append `_v2` (major changes only, doc 02 §4).

## 3. Principals

### Groups (synced from IdP/AAD)

| Group | Typical members |
|---|---|
| `grp_<org>_stewards` | Data owners; approve intake, resolve conflicts |
| `grp_<org>_modelers` | Approve mappings; own entity specs (with design authority) |
| `grp_<org>_engineers` | Merge pipeline PRs; incident response |
| `grp_<org>_analysts` | Consume gold |
| `grp_edw_platform` | Platform admins (agent factory, meta, CI) |
| `grp_edw_design_authority` | Cross-org entity model owners |

### Service principals — the security core

| SP | Used by | Grants |
|---|---|---|
| `sp_<org>_ingest` | Bronze ingestion jobs | WRITE `<org>_bronze` only |
| `sp_<org>_runtime` | Prod DLT pipelines | READ `<org>_bronze`; WRITE `<org>_silver`; WRITE `ref_master.km_*`/hub upserts via governed pipeline only; no gold |
| `sp_<org>_gold` | Gold refresh | READ `<org>_silver`, `ref_master`; WRITE `<org>_gold` |
| `sp_<org>_agent` | A1–A6 build-time | READ UC metadata org-wide; `sample_rows` on `<org>_bronze` (masked, row-limited — enforced in tool code); WRITE `<org>_dev` only; git via PR-only token |
| `sp_sentinel` | A7 | READ `edw_meta`, UC metadata all orgs; **no data access**; issue-tracker write |
| `sp_meta` | Controller, sync jobs | RW `edw_meta`; UC comment/tag write |

Hard rules: no SP spans org data boundaries except `ref_master` writes, which go through a single
governed hub-management pipeline. No human has write on prod catalogs; humans change prod only
via PR → CI. Agent SPs have **zero** prod write anywhere.

## 4. Grant script pattern (excerpt, per org)

```sql
-- consumers
GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG pubmkt_gold  TO `grp_pubmkt_analysts`;
-- engineers debug read
GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG pubmkt_silver TO `grp_pubmkt_engineers`;
GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG pubmkt_bronze TO `grp_pubmkt_engineers`;
-- runtime
GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG pubmkt_bronze TO `sp_pubmkt_runtime`;
GRANT ALL PRIVILEGES ON CATALOG pubmkt_silver TO `sp_pubmkt_runtime`;
-- build-time agent: dev sandbox only
GRANT ALL PRIVILEGES ON CATALOG pubmkt_dev TO `sp_pubmkt_agent`;
GRANT SELECT ON CATALOG pubmkt_bronze TO `sp_pubmkt_agent`;  -- masked + row-limited via tool layer
```

Grants themselves are code: a `grants/` directory per org in `edw-pipelines`, applied by CI —
reviewable, versioned, revertible. A5 proposes gold grants only through this path.

## 5. Sensitive data

- `classification` from the contract (from the firm's data-classification scheme) becomes a UC tag;
  column masks / row filters are generated from it by the same grant pipeline.
- The profiling engine reads under an elevated, audited SP but **emits only aggregates**; the LLM
  never receives raw restricted values. `sample_rows` respects masks.
- PII scan disagreement with human classification blocks contract compilation (A2) and routes to
  the steward + data governance.

## 6. Cross-org sharing

Everything cross-org goes through `ref_master` (identity + reference data) or through an explicit
gold-to-gold share with a signed-off use-case spec naming both orgs. Default is deny; the
information barrier is auditable as: "list all grants on `<org>_*` catalogs to principals outside
`<org>`" — a scheduled audit query that should return only documented exceptions (runbook R9).
