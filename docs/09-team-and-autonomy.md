# 09 — Team Structure and Graduated Autonomy

The staffing model and the autonomy model are one design: every human role keeps only the
decisions that agents cannot (or must not) make, and each of those decisions has an explicit
autonomy level with promotion/demotion criteria.

**The objective is not headcount reduction — it is eliminating human-typed code and minimizing
human-typed text (ADR-8).** Humans direct, edit, approve, and audit; agents draft and type.
Headcount effects (the §3 taper) are an outcome, not the goal: the same people redirect from
typing to judgment, and throughput per person rises instead.

## 1. Organization

```
                      EDW Design Authority (governance body)
                      entity model, majors, precedence, autonomy sign-off
                                        │
   ┌────────────────────────────────────┼──────────────────────────────────┐
   │                                    │                                  │
 EDW Platform Pod (central)      Modeling (central)              Org-aligned roles (per org:
 - platform engineers            - modelers                      pubmkt / pvtmkt / pe)
 - ops engineers (shared         - (A8 Reviewer works            - data stewards (part-time)
   on-call rotation)               under this function)          - org design-authority rep
 - owns: agent factory,          - owns: entity specs,           - org engineer liaison
   templates, controller,          mapping approvals,              (Phase 1–2 only)
   CI, edw_meta, A1–A10            tiering appeals
                                        │
                      Data Governance / Risk (existing enterprise function)
                      classification disputes, barrier audit (R9),
                      autonomy-policy risk acceptance (§4)
```

## 2. Role cards

### Platform engineer (central pod)
Owns everything that makes the agents work: runner framework, skills, Jinja templates, JSON
Schemas, controller, CI/CD, `edw_meta`, golden sets, model-version pins. Handles A8/A9 policy
implementation. Skills: Python, Spark/Databricks, prompt/skill engineering, CI. This role grows
in importance as autonomy rises — every automated decision is code/policy they own.
Per ADR-8 they direct rather than type: platform code is authored with Claude Code against the
repo's `CLAUDE.md` conventions; skill edits are drafted by A10. The engineer's non-delegable
work is review — every platform PR is human-reviewed with golden replay as the merge gate,
because you can only supervise code you could have written.

### Ops engineer (central pod, shared across orgs)
Works the exceptions queue: PRs that failed auto-merge policy, A9 playbook steps awaiting
approval, novel incidents (incident command), R6 executions, backfill swaps. Holds the on-call
rotation. Skills: Databricks operations, SQL, incident management.

### Modeler (central)
Two jobs only: evolve entity specs — editing A10 drafts, never authoring from blank pages
(ADR-8) — and review the mapping exceptions A8 escalates (disagreements, low confidence, custom
SQL, `ref_master` entities, Tier promotions). Audits the A8 random sample monthly. Skills: data
modeling, the org's domain. Writes no code; the escape-hatch `mapping.yml` (hand-declared spec
when A3 fails) is the only artifact they may author directly.

### Data steward (org-aligned, part-time)
Confirms pre-filled intakes (10-min target), resolves compile conflicts, owns classification
calls, ranks onboarding priority. The only role that must exist inside each org from day one.

### Design authority (governance body, fortnightly)
Modelers + one rep per org + platform lead. Decides: entity proposals, semver-major changes,
current-view precedence, tier appeals, and **autonomy level changes (§4) — jointly with Risk.**

## 3. Headcount by phase

| Role | Phase 1 (pilot) | Phase 2–3 (scale-out) | Steady state (L2 autonomy) |
|---|---|---|---|
| Platform engineers | 2 | 3 | 2–3 |
| Ops engineers | (covered by platform) | 2–3 per rotation | ~2 |
| Modelers | 1 | 2 | ~1 |
| Org engineer liaison | 1 (pilot org) | 1 per org | 0 (absorbed into pod) |
| Stewards | 1 (pilot org) | part-time per org | part-time per org |
| Design authority | forming | fortnightly, ~0.2 FTE/member | same |
| **Total FTE (excl. stewards)** | **~4–5** | **~8–11** | **~6–8** |

Phase 2–3 is deliberately the peak: humans verify everything while golden sets and agreement
statistics are being accumulated; autonomy promotions then shrink the steady state.

## 4. Graduated autonomy

### Levels

- **L0 — Human decides.** Agent proposes; a named human approves every instance.
- **L1 — Human on exception.** Auto-approve when *all* policy conditions hold (proposer
  confidence, A8/A6 concurrence, risk class); humans see disagreements, exceptions, and a
  **10% random audit sample** reviewed within 5 business days.
- **L2 — Human on audit.** As L1 with audit sample reduced to 2–5%; quarterly policy review.

### Decision × level matrix (target state)

| Decision | Proposer | Checker | Target level | Never automated |
|---|---|---|---|---|
| Intake confirmation | A1 pre-fill | steward | **L0 permanently** | Business meaning & classification are human ground truth |
| Tier-3 conformed mapping | A3 | A8 | L2 | — |
| Tier-1 mapping approval | A3 | A8 | L1 | `custom_transform`, `ref_master` entities, tier promotions stay L0 |
| Pipeline PR merge (minor, rendered-only) | A4 | A6 + policy bot | L2 | — |
| Pipeline PR merge (major / custom SQL / template change / mass regen) | A4 | A6 | **L0 permanently** | High blast radius |
| Runbook R3 quarantine triage | A9 | gates in playbook | L1 | — |
| Runbook R4 backfill (up to shadow + reconcile) | A9 | A6 reconciliation | L2 | Atomic swap stays L0→L1 (approval click) |
| Minor drift absorption (R2) | A7→A4 | A6 | L1 | — |
| Entity spec changes | agent-drafted | design authority | **L0 permanently** | The stable core; systemic blast radius |
| Grants / access (R9) | A5 proposes | data owner + platform | **L0 permanently** | Information barrier |
| Incident command (novel) | — | — | human | Accountability, operational-resilience obligations |

### Promotion criteria (per decision type, per org)

L0→L1: ≥200 consecutive decisions where the human verdict agreed with the would-be automated
verdict ≥95%; zero majors mis-classified; golden set covering the decision type; policy document
signed by design authority + Risk. L1→L2: ≥3 months at L1 with clean audit samples and no
demotion triggers.

### Demotion triggers (automatic, any one suffices)

Audit sample finds a material error; any production incident root-caused to an automated
decision; model or skill version change (drops one level until golden replay + 50-decision
re-qualification); drift in agreement rate below 90%.

### Accountability record

Every automated decision writes to `edw_meta.agent_audit`: decision type, autonomy level,
policy version, proposer/checker skill+model versions, inputs hash, sampled-for-audit flag,
auditing human (if sampled). The answer to "who approved this?" is always reconstructible:
either a named person, or "policy vX.Y at L1, signed off by <design authority + Risk> on
<date>, audit-sampled by <person>".

## 5. The reviewer/operator/drafter agents (specs in doc 03 §2)

- **A8 Reviewer** — independent critic for A3's mappings. Different skill and prompt from A3
  (proposer/critic separation); checks entity choice, key logic vs observed duplicates,
  cross-source consistency, semantic plausibility. Its agree/disagree verdict versus the human
  decision is the statistic that earns L1.
- **A9 Operator** — executes runbooks R2 (minor), R3, R4 as playbooks with hard verification
  gates (A6 checks) and approval points per the matrix above. Never acts outside a playbook;
  novel situations page the ops engineer.
- **A10 Drafter** — eliminates blank pages (ADR-8): drafts entity specs from cross-source
  profiles, use-case specs from consumer interviews, and skill edits from harvested corrections.
  Permanently L0 — its drafts are always human-edited and human-merged.

## 6. Who types what — the ADR-8 matrix

| Artifact | Drafted/typed by | Human role |
|---|---|---|
| Pipeline code, tests, expectations, gold views, grants | Renderer (from specs) | None — CI rejects hand-edits (provenance hash) |
| Mappings | A3 | Approve/edit (A8 + policy at L1+) |
| Entity specs, use-case specs | A10 | Edit + merge (permanent) |
| Intakes | A1 pre-fill | Correct via structured form; write business-meaning prose (permanent, ground truth) |
| Skills/prompts | A10 (`skill-refinement`) | Review diff + golden replay, merge |
| Platform code (agent factory, templates, CI) | Claude Code, engineer-directed | Review every PR (permanent) |
| Runbook playbooks | Written once (Claude Code), executed by A9 | Approve gated steps per autonomy level |
| `custom_transform` SQL | A3 (occasionally human) | Line-by-line review (permanent L0) |

## 7. North-star metrics (ADR-8)

- **Human-authored lines merged per month, per repo** — target ~0 for `edw-specs` structured
  content and `edw-pipelines` (enforced); small but non-zero for `edw-agent-factory`.
- **Edit distance on agent drafts** — per artifact type; trending to zero flags an autonomy
  promotion candidate, staying high flags a skill that needs work (feeds R7).
- **Blank-page violations** — artifacts created without an agent draft; should be zero except
  documented escape hatches (modeler's hand-declared mapping).
- **Unresolved `TODO(human)` age** — A10 drafts waiting on human ground truth.

These join the doc 08 §2 dashboard; reviewed monthly alongside autonomy statistics.

## 8. On-call and escalation

Ops pod runs a weekly on-call rotation covering all orgs (Sentinel routes by severity;
org-specific context comes from runbook metadata and steward contacts in the contract).
Escalation: on-call → platform lead → design authority chair (data issues) or Risk (barrier /
classification issues). Anything `awaiting` a human > 5 business days appears in the weekly ops
review; autonomy statistics reviewed monthly; levels reviewed quarterly (ops manual §3).
