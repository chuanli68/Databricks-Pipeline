---
# S4 entity spec (A10-drafted, modeler-edited). Prototype instance of templates/entity.md
entity: instrument
version: 1.0.0
domain: instrument
shared: true                      # hub + km live in ref_master (ADR-5)
business_key:
  definition: "ISIN, upper-trimmed (prototype simplification of the enterprise instrument id)"
  columns: [isin]
hub: ref_master.instrument.h_instrument
key_map: ref_master.instrument.km_instrument
attributes:
  - {name: name,       type: string, description: "Official instrument name"}
  - {name: currency,   type: string, description: "ISO 4217"}
  - {name: sector_raw, type: string, description: "Vendor sector; canonical asset class resolved via ref_master.reference.asset_class"}
  - {name: close_px,   type: double, description: "EOD close", scd: true}
current_view_precedence:
  default: [bloomberg, refinitiv]
---
## Definition and scope
Any tradable security the firm can hold in public markets. Private-market funds/deals are NOT
instruments — they are `fund` / `deal` entities owned by pvtmkt.
