---
# S4 — Entity spec. Owned by modelers / design authority. THE stable artifact — semver-major gated.
entity: instrument
version: 1.0.0
domain: instrument
shared: true                       # physical hub + key map live in ref_master
business_key:
  definition: "Enterprise instrument identifier; composite fallback ISIN||MIC||currency when unassigned"
  columns: [enterprise_instrument_id]
hub: ref_master.instrument.h_instrument
key_map: ref_master.instrument.km_instrument
links:
  - {name: instrument_issuer, to_entity: party, cardinality: "N:1"}
attributes:                        # the canonical attribute dictionary — satellites map INTO these
  - {name: name,        type: string,        description: "Official instrument name"}
  - {name: asset_class, type: string,        description: "Enterprise asset class taxonomy L1", domain_values_ref: ref_master.reference.asset_class}
  - {name: currency,    type: "char(3)",     description: "Denomination currency, ISO 4217"}
  - {name: close_px,    type: "decimal(18,6)", description: "EOD close", scd: true}
current_view_precedence:           # per-attribute source priority for v_instrument_current
  default: [internal_master, bloomberg, refinitiv]
  overrides:
    close_px: [bloomberg, refinitiv]
---

## Definition and scope
What is (and is not) an instrument for the firm. Edge cases: private placements, derivatives legs, …

## Change log rationale
Why each major change was made; design-authority minutes links.
