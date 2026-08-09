# 08 — Operations Manual

## 1. Runbooks

### R1 — Onboard a new source feed
Actor: steward initiates. 1) Insert row in `onboarding_state` (`REGISTERED`) via the onboarding
notebook/form, with org, source system, connection ref, priority. 2) Controller runs A1;
steward receives pre-filled `intake.md` PR — review grain, meaning, classification, SLA (target
10 min), merge. 3) If `COMPILE_BLOCKED`: resolve the named conflict (fix intake or accept
discovered fact), re-merge. 4) Modeler reviews mapping PR (Tier 1) — check entity choice,
business key, low-confidence mappings listed at top. 5) Engineer merges pipeline PR after green
A6 report. Verify: state `LIVE`, first run reconciles, gold unaffected.

### R2 — Source schema drift detected
Trigger: Sentinel issue with change class. Minor (additive): auto-PR already open — steward
merges intake/contract bump; regen + deploy flows automatically; verify satellite evolved, no
other table touched. Major: Sentinel routes per doc 06 §4 table; engineer follows the named
path (deprecate column / new sat version / R6). Never hand-edit generated code — fix the
mapping or template and regen.

### R3 — DQ expectation failures spike
Executed by A9 Operator as a playbook once qualified (doc 09 §4); ops engineer approves gated
steps at L0, reviews audit sample at L1+. Trigger: Sentinel alert (failure rate > threshold in contract). 1) Check quarantine rows —
data problem vs rule problem. 2) Data problem: raise to source owner listed in contract;
quarantined rows replay automatically on next run once fixed. 3) Rule problem (legit data
rejected): patch contract `checks` (patch/minor bump), regen expectations. 4) Postmortem row in
`edw_meta.dq_incidents` if consumer-visible.

### R4 — Rebuild / backfill one satellite
Executed by A9 Operator up to step 3; the atomic swap (step 4) requires an ops-engineer approval
until that step reaches L1 (doc 09 §4). 1) Confirm blast radius is the one satellite (query lineage). 2) Run bundle's backfill job with
`--from-date` → shadow table `s_x__y__rebuild`. 3) A6 reconciliation: counts, SCD integrity,
spot-check hash_diffs vs live. 4) Atomic swap (RENAME), keep old table 30 days. 5) Gold
materialized views refresh on schedule; verify `v_<entity>_current` unchanged for untouched
attributes.

### R5 — Promote a Tier-3 table into the canonical model
Trigger: A5 refusal issue (use case needs unmapped data) or steward request. 1) Modeler confirms
target entity exists (else entity proposal → design authority). 2) Set tier decision to 1 in
`tiering/tier-decisions.yml`; controller re-enters feed at `CONTRACTED`; A3 proposes mapping;
normal flow resumes. Conformed table stays live until gold consumers cut over.

### R6 — Grain or business-key change (the most dangerous change)
Human-led; agents only assist. 1) Freeze feed onboarding row. 2) Treat as **new source
generation**: new contract major, new satellites (and km entries) built in parallel with old.
3) Run old + new side by side ≥ 1 full cycle; A6 cross-reconciliation. 4) Flip current-view
precedence to new generation; freeze old satellites (queryable history). 5) Design-authority
sign-off recorded in the contract changelog.

### R7 — Agent misbehavior / bad merged artifact
Bad open PR: close it, file defect vs skill, add the case to goldens. Bad merged spec: revert
PR; controller resets state. Bad deployed code: redeploy previous bundle tag; if bad data was
written, scope is by construction ≤ affected satellites → R4. Then: root-cause in skill or
template, fix, replay goldens, regen. Monthly: harvest all human edits to agent PRs into
goldens; A10's `skill-refinement` mode drafts the resulting skill edits, platform engineer
reviews and merges (ADR-8).

### R8 — Model or skill upgrade
1) Branch skill/model-version pin. 2) Replay full golden set; diff report reviewed by platform
eng. 3) Canary: run new version on 10 live feeds' next cycles in shadow (outputs compared, not
merged). 4) Promote pin; record in `edw_meta.agent_audit`.

### R9 — Access request / barrier audit
Requests via grants-as-code PR only (doc 05 §4); approver = data owner of target catalog +
platform. Scheduled audit query lists cross-org grants; any row not matching a documented
exception → incident to governance. Quarterly recertification of group memberships.

### R10 — Bronze source decommission
1) Contract state → `RETIRED`; ingestion stops; satellites frozen `is_current` as-of date.
2) Current-view precedence updated (design authority if Tier 1). 3) Bronze retained per
retention policy (replay log). 4) Gold views referencing only this source fail CI at regen —
consumers notified via use-case spec owners.

## 2. Monitoring and SLOs

| Signal | Source | SLO / alert |
|---|---|---|
| Pipeline freshness vs contract SLA | DLT event logs vs `contract.sla` | Alert on breach; Sentinel files R3/R2 |
| Expectation pass rate | `edw_meta.dq_events` | < 99% warn, < 95% page (per contract override) |
| Onboarding queue age | `onboarding_state` | `awaiting` human > 5 bd → weekly review |
| Agent job failures / retry loops | `edw_meta.agent_audit` | 3 consecutive failures → platform eng |
| LLM spend per org/agent | `agent_audit` | Budget alarm |
| Drift backlog | Sentinel issues open | > 20 per org → prioritization session |
| Barrier audit | R9 query | Any unexpected row → immediate |

Dashboards (Databricks SQL / Lakeview): Onboarding funnel by state; DQ heatmap by
org × source; Agent quality (acceptance rate, edit distance on PRs, golden regression);
Cost. Nightly digest email/Slack per role: stewards (intakes waiting), modelers (mappings
waiting), engineers (PRs + incidents).

## 3. Routine cadence

Daily: Sentinel digest triage (ops engineer on duty). Weekly: ops review — queue ages,
DQ trends, cost. Fortnightly: design authority — entity proposals, majors, precedence rules,
autonomy decisions. Monthly: golden harvest (R7), A8/A9 audit-sample review + agreement-rate
report (doc 09 §4), grant recertification sampling, template debt review. Quarterly: full R9
recertification; autonomy policy review; disaster drill (restore a satellite from bronze
replay, R4).
