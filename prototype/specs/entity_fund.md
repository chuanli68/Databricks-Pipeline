---
# S4 entity spec — org-specific entity (hub inside pvtmkt_silver, not shared)
entity: fund
version: 1.0.0
domain: fund
shared: false
business_key:
  definition: "eFront fund code, upper-trimmed"
  columns: [fund_code]
hub: pvtmkt_silver.fund.h_fund
key_map: pvtmkt_silver.fund.km_fund
attributes:
  - {name: fund_name,   type: string}
  - {name: vintage,     type: int}
  - {name: currency,    type: string}
  - {name: asset_class, type: string, description: "ref_master.reference.asset_class.code"}
  - {name: nav_musd,    type: double, scd: true, description: "Quarterly NAV; SCD2 gives restatement history"}
current_view_precedence:
  default: [efront]
---
## Definition and scope
A private-markets fund vehicle the firm has committed to. Deals are a separate entity
(currently Tier 3, conformed) linked by fund_code; promote via R5 when a use case needs it.
