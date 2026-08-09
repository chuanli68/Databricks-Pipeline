# 04 — Orchestration

## 1. Design: state table + controller, not a DAG

Source onboarding is long-running (days — it contains human gates), so it cannot be a single job
DAG. The unit of orchestration is a **state machine row per source feed** in
`edw_meta.onboarding_state`; a **controller job** (runs every 10 min + event-triggered) looks for
rows whose state has a runnable next action and launches the corresponding agent job.

```sql
CREATE TABLE edw_meta.onboarding_state (
  source_feed_id   STRING,   -- org.source_system.feed
  state            STRING,   -- see §2
  state_since      TIMESTAMP,
  awaiting         STRING,   -- NULL | 'steward' | 'modeler' | 'engineer' | 'agent_retry'
  contract_version STRING,
  active_pr        STRING,
  attempt          INT,
  last_error       STRING,
  updated_by       STRING    -- job/agent/human id — full history via Delta CDF
);
```

## 2. States and transitions

| State | Advanced by | Next |
|---|---|---|
| `REGISTERED` | Controller launches A1 | `DISCOVERED` |
| `DISCOVERED` | Steward confirms intake (PR merge) | `INTAKE_CONFIRMED` |
| `INTAKE_CONFIRMED` | Controller launches A2 | `CONTRACTED` \| `COMPILE_BLOCKED` |
| `COMPILE_BLOCKED` | Human resolves conflict issue | `INTAKE_CONFIRMED` (recompile) |
| `CONTRACTED` | Controller launches A3 (A8 reviews the proposal) | `MAPPING_PROPOSED` |
| `MAPPING_PROPOSED` | Modeler approves — or auto-approve at L1+ when A8 concurs + policy holds (§2.1) | `MAPPED` |
| `MAPPED` | Controller launches A4→A6 loop | `VALIDATED` \| `VALIDATION_FAILED` |
| `VALIDATION_FAILED` | ≤3 auto-retries, then engineer | `MAPPED` (retry) |
| `VALIDATED` | Engineer merges — or auto-merge for low-risk classes at L1+ (§2.1) | `DEPLOYED` (CI) |
| `DEPLOYED` | First successful prod run | `LIVE` |
| `LIVE` | Sentinel events | re-enter at `DISCOVERED`/`MAPPED` per change class |

Human gates are exactly the three `awaiting` values; a nightly digest per role lists everything
waiting on them (ops manual §3). Escalation: anything `awaiting` a human > 5 business days
surfaces in the weekly ops review.

### 2.1 Approval and merge policy (enforced by a policy bot, versioned in `edw-agent-factory/policies/`)

| Risk class | Conditions | L0 | L1 | L2 |
|---|---|---|---|---|
| Mapping, Tier 3 | A8 concurs | modeler | auto + 10% audit | auto + 2–5% audit |
| Mapping, Tier 1 standard | A3 confidence ≥0.8 all columns, A8 concurs, no custom SQL, not `ref_master` | modeler | auto + 10% audit | auto + 2–5% audit |
| Mapping, sensitive | custom SQL, `ref_master` entity, tier promotion | modeler | modeler | modeler |
| PR merge, low-risk | rendered-only diff, minor change class, green A6, single satellite/conformed target | engineer | auto + audit | auto + audit |
| PR merge, high-risk | major, custom SQL, template change, mass regen, grants | engineer | engineer | engineer |

Autonomy levels are per decision type × org, stored in `edw_meta.autonomy_policy`, changed only
by design authority + Risk sign-off (doc 09 §4). The policy bot records every automated approval
in `agent_audit` with the policy version.

## 3. Event wiring

- **Git → controller:** webhook (GitHub Actions job) writes PR-merged events to
  `edw_meta.git_events`; controller consumes and advances state.
- **DLT → Sentinel:** pipeline event logs and expectation metrics land in `edw_meta.dq_events`
  (DLT event log table + a small extractor job).
- **Schedules:** drift detector nightly per org; UC sync hourly; controller every 10 min.
- **Concurrency:** controller processes feeds independently; per-org concurrency cap (default 20
  active onboardings) to keep review queues humane; priority column for steward-ranked ordering.

## 4. CI/CD (edw-pipelines)

```
PR opened (by A4/A5)
 ├─ renderer provenance check (ADR-8): every generated file carries a header hash of
 │    (mapping version, template version, renderer version); CI recomputes and rejects
 │    any file that was hand-edited or not produced by the renderer
 ├─ databricks bundle validate
 ├─ unit tests (pytest, local Spark)  ── generated fixtures from contract
 ├─ deploy → <org>_dev sandbox
 ├─ A6 integration validation (report posted to PR; required check)
 └─ human review (engineer; modeler already approved the mapping)
merge → main
 ├─ deploy → test env, run on full sample
 └─ tag release → deploy prod (bundle) — scheduled or manual per org policy
```

- One Asset Bundle per **org × domain** (e.g. `pubmkt-instrument-pricing`) — bounded blast
  radius, independent deploy cadence, clear code ownership.
- Bundle targets `dev`/`test`/`prod` map to the catalog sets in doc 05; the same generated code
  runs everywhere with only the target catalog parameterized.
- Rollback = redeploy previous bundle tag (runbook R7). Data rollback is per-satellite (R4).

## 5. Environments

| Env | Catalogs | Data | Who |
|---|---|---|---|
| dev | `<org>_dev` | Profiled samples, synthetic fixtures | Agents (A6), engineers |
| test | `<org>_test_*` | Full copies of in-scope feeds | CI only |
| prod | `<org>_bronze/silver/gold` | Production | Runtime SPs only |

## 6. Cost and rate control

- Agent jobs run on small job clusters / serverless; model calls metered per agent in
  `edw_meta.agent_audit` (tokens, latency, cost) — dashboarded (ops manual §3).
- Budget alarms per org; A3 (top-tier model) is the cost driver — its per-feed cost is cents
  versus hours of modeler time, but monitor for pathological retry loops (cap: 3).
