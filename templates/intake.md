---
# S1 — Human intake template. Pre-filled by A1 Profiler; steward corrects and confirms.
# Only fields agents CANNOT discover. Target completion time: 10 minutes.
source_feed_id: pubmkt.bloomberg.eod_prices        # org.source_system.feed
owner: ""                                          # accountable person/team (required)
steward: ""                                        # who confirms this file (required)
grain: ""                                          # e.g. "one row per instrument per trading day" (required)
declared_keys: []                                  # business key columns, e.g. [instrument_id, price_date]
classification: internal                           # per enterprise data classification scheme (required)
sla: ""                                            # e.g. "T+1 by 07:00 SGT"
usage_restrictions: []                             # e.g. ["not for NAV calculation"]
intended_entities: []                              # steward's guess, e.g. [instrument, valuation]; A3 may differ
retention_note: ""                                 # only if deviating from default (bronze kept forever)
confirmed_by: ""                                   # steward id — merging the PR constitutes confirmation
---

## Business context  <!-- what the data means, in prose; agents reason over this -->

## Known quirks      <!-- half-days, vendor restatements, timezone traps, … -->
