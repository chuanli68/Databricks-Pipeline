---
# S6 — Use-case spec. Written by consumer team + steward. Sole input to A5 gold projection.
use_case: daily_pm_risk_snapshot
org: pubmkt
version: 1.0.0
consumer_group: grp_pubmkt_analysts        # A5 generates grants ONLY to this group
freshness: "T+1 by 08:00 SGT"
entities:
  - {name: position, grain: "portfolio × instrument × date", history: current_only}
  - {name: instrument, attributes: [name, asset_class, currency, close_px], history: current_only}
  - {name: valuation, history: "scd2, 2 years"}
filters:
  - "portfolio in public markets book hierarchy"
target:
  catalog: pubmkt_gold
  schema: risk_snapshot
  objects:
    - {name: v_daily_position_risk, type: materialized_view, refresh: "on silver update"}
---

## Purpose and definitions
What questions this answers; metric definitions consumers rely on.

## Out of scope
Explicitly excluded data/joins (prevents scope creep in regeneration).
