# 02 — Spec System

Specs are the interface between humans, agents, and codegen. Every spec is a file in `edw-specs`,
schema-validated in CI, semver-versioned, and merged only via PR.

## 1. The six artifacts

| # | Artifact | File | Author | Consumer | Volatility |
|---|---|---|---|---|---|
| S1 | Human intake | `intake.md` (YAML frontmatter + prose) | Steward (pre-filled by A1) | A2 | Low |
| S2 | Discovery snapshot | `discovery.yml` | A1 (deterministic engine + LLM notes) | A2, A7 | Regenerated on drift |
| S3 | Source contract | `contract.yml` | A2 (compiled) | A3, A4, A7, UC sync | Semver-managed |
| S4 | Entity spec | `entity.md` | A10-drafted, modeler-edited (ADR-8) | A3, A4, A5 | **Very low — this is the stable core** |
| S5 | Mapping spec | `mapping.yml` | A3 (human-approved / A8 at L1+) | A4 renderer | Medium — absorbs source change |
| S6 | Use-case spec | `use-case.md` | A10 interview-drafted, consumer team + steward edited | A5 | Per use case |

Per ADR-8, no spec starts from a blank page: A1 pre-fills S1, A10 drafts S4 and S6. The intake
UI should favor structured inputs (dropdowns from the classification scheme, key pickers from
discovered columns) so even human edits are selections, not typing — free prose remains only
where it is ground truth (business context, quirks).

Templates for all six are in [`templates/`](../templates/).

## 2. Repo layout (`edw-specs`)

```
edw-specs/
├── orgs/
│   ├── public_markets/
│   │   ├── sources/<source_system>/<feed>/
│   │   │   ├── intake.md
│   │   │   ├── discovery.yml          # regenerated; committed for audit
│   │   │   ├── contract.yml           # canonical, semver
│   │   │   └── mappings/<entity>.yml  # one per target entity
│   │   └── use-cases/<name>/use-case.md
│   ├── private_markets/ ...
│   └── private_equity/ ...
├── entities/                          # org-shared canonical model
│   ├── instrument.md
│   ├── party.md
│   ├── portfolio.md
│   ├── position.md
│   ├── transaction.md
│   ├── valuation.md
│   └── pe/{fund.md, deal.md, portfolio_company.md}
├── schemas/                           # JSON Schemas validating all YAML above
└── tiering/tier-decisions.yml         # A3 outputs, one line per source table
```

Entity specs live **outside** org directories deliberately: instrument and party identity is
shared across orgs (physical hubs live in `ref_master`, doc 05). Org-specific entities may live
under `entities/<org>/`.

## 3. Provenance

Every field in `contract.yml` carries provenance: `human` | `discovered` | `agent` |
`agent_human_approved`. Rules:

- Drift automation may auto-update only `discovered` fields (via version-bump PR).
- `human` fields are never modified by any agent; agents may only open an issue proposing a change.
- Reviewers focus on `agent` fields; `discovered` fields are trusted (deterministic origin).

## 4. Versioning and change classes

`contract.yml` and `entity.md` are semver-versioned. The version drives what regenerates:

| Change | Bump | Downstream effect |
|---|---|---|
| Description/doc only | patch | UC sync only; no codegen |
| New column in source | minor | A4 regenerates bronze + affected satellite DDL (additive `mergeSchema`); no reload |
| Column type widened | minor | Satellite column evolves; no reload |
| Type narrowed / column dropped / renamed | major | New satellite version `s_<entity>__<source>_v2`; old satellite frozen, history preserved; mapping regenerated |
| Business key or grain change | major | **Human required.** Treated as a new source generation; runbook R6 |
| Entity spec change | major only by design authority | Modeler-led; A3 re-proposes affected mappings |

The invariant behind every row of this table: **hubs and other sources' satellites are never
touched.** There is no change class that triggers a warehouse reload.

## 5. Spec lifecycle state machine

```
DRAFT → VALIDATED (CI schema check) → PROPOSED (PR open) → ACTIVE (merged)
   ACTIVE → SUPERSEDED (newer version merged) → RETIRED (source decommissioned)
Conflict at compile: A2 emits no contract; state COMPILE_BLOCKED + issue.
```

## 6. Spec ↔ Unity Catalog sync

The UC sync job (deterministic) projects `contract.yml` into the platform so specs are not a
side-car artifact:

- Column `description` → UC column comments (searchable, used by Genie).
- `classification`, `sla`, `owner`, `tier` → UC tags.
- Reverse check: if someone edits a UC comment by hand, sync flags divergence and opens a spec
  issue — git remains the source of truth.
