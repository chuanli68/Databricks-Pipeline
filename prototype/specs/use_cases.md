---
# S6 use-case specs (both orgs, condensed)
use_cases:
  - use_case: daily_pm_risk_snapshot
    org: pubmkt
    consumer_group: pubmkt analyst user (grp_pubmkt_analysts in production)
    freshness: "T+1 by 08:00 SGT"
    entities:
      - {name: instrument, attributes: [name, currency, sector_raw, close_px], history: current_only}
      - {name: positions (conformed), grain: "portfolio × instrument × date"}
    reference: [ref_master.reference.asset_class]
    target: {catalog: pubmkt_gold, schema: risk_snapshot,
             objects: [v_daily_position_risk]}

  - use_case: fund_performance
    org: pvtmkt
    consumer_group: pvtmkt analyst user (grp_pvtmkt_analysts in production)
    freshness: "on silver update"
    entities:
      - {name: fund, history: "scd2 full"}
      - {name: deals (conformed)}
    reference: [ref_master.reference.asset_class]
    target: {catalog: pvtmkt_gold, schema: fund_performance,
             objects: [v_fund_nav_history, v_deal_pipeline]}
---
## Purpose
Risk snapshot: positions valued at latest close with asset-class rollup.
Fund performance: NAV history incl. restatements (SCD2), deal pipeline by fund.
