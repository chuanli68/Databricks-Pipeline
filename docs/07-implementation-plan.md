# 07 — Implementation Plan

## Phase 0 — Foundation (weeks 1–6)

Deliverables: metastore + catalog matrix and grants (doc 05); three repos scaffolded; JSON
Schemas for all six spec types; agent runner framework + tool library with scoping enforced;
`edw_meta` tables + controller skeleton; CI/CD skeleton (bundle validate → dev deploy);
Mosaic AI external-model endpoint for Claude approved through the firm's model-governance process.

Exit criteria: a hand-written mapping.yml renders through templates, deploys to dev, passes A6
checks end-to-end. No LLM required yet — **prove the deterministic spine first.**

## Phase 1 — Pilot, one domain (weeks 7–14)

Scope: public markets, instrument + valuation entities, 3–5 real feeds (e.g. two price vendors +
one internal position source — deliberately overlapping so hub/satellite value is demonstrated).

- Entity specs for pilot entities: A10-drafted from cross-source profiles and vendor
  dictionaries, modeler-edited (ADR-8; A10's entity-drafting skill comes online here).
- Bring A1–A6 online one at a time, in order; each agent's output is human-verified 100% during
  this phase. Build first golden sets from these reviews.
- One real gold use case shipped to a friendly consumer team.

Exit criteria: new feed onboarded end-to-end in < 5 working days with ≤ 3 human touch points;
a simulated vendor schema change absorbed with zero reload of untouched tables (rehearse R2/R4).

## Phase 2 — Industrialize (weeks 15–26)

- Sentinel (A7) + drift detector + UC sync live; nightly digests; dashboards (ops §3).
- Golden-set CI for skills; harvest-corrections loop running monthly.
- **A8 Reviewer in shadow mode**: reviews every mapping alongside the human; agreement
  statistics accumulate toward L1 (doc 09 §4). A9 Operator runs playbooks with per-step
  human approval.
- Scale to ~50 feeds across 2 orgs; onboard `pe` or `pvtmkt` to prove the org-isolation model
  (separate SPs, catalogs, review groups).
- Tier-3 conformed-silver path fully automatic (steward approves intake; no modeler needed).

Exit criteria: Tier-3 feed onboards with ~1 human touch point; mapping-approval queue < 1 week;
agent PR acceptance rate > 80% without edits.

## Phase 3 — Scale-out (months 7–12)

- Bulk registration of source systems; prioritized backlog driven by gold use-case demand
  (demand-pull, ADR-4). Target: hundreds of feeds live; long tail flowing as conformed silver.
- Entity model grows under design authority cadence (§ below); template upgrades exercised as
  mass regen PRs at least once (proves fleet-wide maintainability).
- **First autonomy promotions**: Tier-3 mappings and low-risk PR merges to L1 once criteria met
  (doc 09 §4); R3/R4 playbook steps to L1. Headcount tapers per the doc 09 §3 table as levels rise.

## Ongoing operating model

Full team structure, role cards, headcount-by-phase, and the graduated-autonomy model are in
[doc 09](09-team-and-autonomy.md). Summary: peak ~8–11 FTE during scale-out (everything
human-verified while agreement statistics accumulate), tapering to **~6–8 FTE at steady state**
(2–3 platform engineers, ~2 ops engineers on shared rotation, ~1 modeler, part-time stewards
per org, fortnightly design authority) once A8/A9 reach L1–L2 on the qualifying decision types.

Design authority meets fortnightly: entity proposals (from A3 issues), major changes, precedence
rules for current views, and autonomy-level decisions (jointly with Risk).

## Top risks and mitigations

| Risk | Mitigation |
|---|---|
| Entity model designed wrong early (worst risk — it's the stable thing) | Pilot on best-understood domain; design authority; entity specs are semver-major-gated |
| Agent mapping quality poor → review burden exceeds savings | Confidence scores route attention; golden-set CI; 100% verification in Phase 1 before trust dial-up |
| Steward bottleneck at intake | Pre-filled intake from A1; 10-min target; nightly digest; escalation at 5 days |
| Hash/SCD subtleties corrupt history silently | A6 SCD integrity checks mandatory; reconciliation counts in every validation |
| Model/vendor change alters agent behavior | Pinned model versions per skill; golden replay before any model upgrade |
| Cost creep (LLM + regen compute) | Per-agent metering, org budgets, retry caps |

## Success metrics (dashboard from day 1)

Onboarding lead time per tier; human touch points per feed; agent PR acceptance rate; % feeds
with zero-reload absorption of source changes (target: 100% by construction); DQ expectation
pass rate; steward/modeler queue depth; cost per onboarded feed; **human-authored lines merged
per repo and edit distance on agent drafts** (the ADR-8 north stars, doc 09 §7).
