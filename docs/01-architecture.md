# 01 — Architecture

## 1. Component inventory

### 1.1 Git repositories (source of truth)

| Repo | Contents | Written by | Reviewed by |
|---|---|---|---|
| `edw-specs` | Source contracts, entity specs, mapping specs, use-case specs, tiering decisions | Agents (PRs) + stewards | Data stewards / modelers |
| `edw-pipelines` | Generated Lakeflow (DLT) pipeline code, tests, Databricks Asset Bundles — one bundle per org × domain | Codegen agent (PRs) | Data engineers |
| `edw-agent-factory` | Agent runner framework, skills (prompt packages), Jinja codegen templates, validators, JSON Schemas | Platform team | Platform team |

### 1.2 Agents (build time — see doc 03 for full specs)

| ID | Agent | Consumes | Produces |
|---|---|---|---|
| A1 | Profiler | Bronze table (sampled), UC metadata | `discovery.yml` + draft descriptions |
| A2 | Contract Compiler | `intake.md` + `discovery.yml` | `contract.yml` (versioned), conflict issues |
| A3 | Entity Mapper | `contract.yml`, entity catalog | Tier decision + `mapping.yml` proposal |
| A4 | Codegen | Approved `mapping.yml`, templates | Pipeline code + tests + expectations (PR) |
| A5 | Gold Projector | `use-case.md`, silver model | Gold views + grants (PR) |
| A6 | Validator | Generated code, dev sandbox | Validation report; iterates with A4 |
| A7 | Sentinel | DQ events, schema drift, freshness | Issues; re-triggers A1/A2; version-bump PRs |
| A8 | Reviewer | A3's mapping proposals | Independent critic verdict; enables auto-approval (doc 09) |
| A9 | Operator | Runbook triggers (R2 minor, R3, R4) | Playbook execution with verification gates (doc 09) |
| A10 | Drafter | Cross-source profiles, data dictionaries, consumer interviews, harvested corrections | Draft entity specs, draft use-case specs, proposed skill edits — all human-edited, never auto-merged |

### 1.3 Deterministic services (no LLM)

| Service | Implementation | Purpose |
|---|---|---|
| Profiling engine | PySpark job | Row counts, null rates, cardinality, candidate keys, distributions, PII regex scan. A1's LLM only interprets its output. |
| Spec validator | JSON Schema + pydantic, runs in CI | Rejects malformed specs before any agent or human sees them |
| Codegen renderer | Jinja2 | `mapping.yml` → SQL/PySpark. Deterministic: same mapping in, same code out |
| CI/CD | GitHub Actions + Databricks Asset Bundles | bundle validate → unit tests → deploy dev → integration test → deploy prod on merge |
| Drift detector | Scheduled job | Diffs live source schema vs `contract.yml`; feeds A7 |
| UC sync | Scheduled job | Pushes contract descriptions/tags into Unity Catalog comments and tags; flags divergence |
| State controller | Databricks Job (Python) | Advances the onboarding state machine (doc 04) |

### 1.4 Databricks platform components

- **Unity Catalog** — governance backbone: catalogs per org × layer, grants, lineage, tags, row filters/column masks (doc 05).
- **Lakeflow Declarative Pipelines (DLT)** — all bronze→silver runtime code, with expectations as the DQ safety net.
- **Lakeflow Connect / Auto Loader** — bronze ingestion from databases and feeds.
- **Databricks Jobs** — agent runners, profiler, controller, sentinel, sync jobs.
- **Databricks Asset Bundles** — packaging + environment promotion (dev/test/prod).
- **`edw_meta` catalog** — operational state: onboarding state, profiling results, validation reports, agent audit log, run ledger.
- **Model access** — Claude via Databricks Mosaic AI external models (governed endpoint, logged, no data leaves approved boundary) — aligns with enterprise control requirements; avoid direct vendor API calls from jobs.

## 2. End-to-end flow (one source, first onboarding)

1. Steward registers source in `edw_meta.onboarding_state` (or Sentinel auto-registers a newly
   landed bronze schema). State: `REGISTERED`.
2. **A1 Profiler** runs engine + drafts `discovery.yml` and pre-filled `intake.md`. State: `DISCOVERED`.
3. Steward edits/confirms `intake.md` (10-minute review of pre-filled form). State: `INTAKE_CONFIRMED`.
4. **A2 Contract Compiler** merges → `contract.yml` v1.0.0, opens spec PR. Conflicts (grain
   mismatch, PII found) block with an issue. Steward merges. State: `CONTRACTED`.
5. **A3 Entity Mapper** classifies Tier 1/2/3 and, for Tier 1, proposes `mapping.yml`
   (entity, business key, column mappings, SCD columns). **Human gate: modeler approves mapping.**
   Tier 3 skips to a conformed-silver mapping (auto-approvable). State: `MAPPED`.
6. **A4 Codegen** renders pipeline code + tests + expectations from templates; **A6 Validator**
   deploys to dev sandbox, runs against sampled data, checks schema/keys/reconciliation; loops
   with A4 (max 3 iterations, then escalates). State: `VALIDATED`.
7. PR to `edw-pipelines`. **Human gate: engineer merges.** CI deploys. State: `DEPLOYED`.
8. **A7 Sentinel** monitors forever: expectation failures, drift, freshness → issues → loop back
   to step 2 or 4 with a semver-scoped change. State: `LIVE`.

Human touch points: intake confirmation (steward), mapping approval (modeler), PR merge (engineer).
Everything else is automated. Under graduated autonomy (ADR-7, doc 09), the mapping-approval and
low-risk PR-merge gates are progressively delegated to A8 Reviewer + merge policy, leaving intake
confirmation as the only permanent per-feed human gate.

## 3. Decision records (summary ADRs)

**ADR-1: Agents operate at build time only.**
Rationale: determinism, auditability, regulatory control expectations, cost. Consequence: runtime
incidents are ordinary pipeline incidents; agent failures can never corrupt data.

**ADR-2: LLM output is specs (YAML), not free-form code.**
Rationale: structured output is schema-validatable; Jinja rendering guarantees uniform, stable
code across thousands of pipelines; review shrinks from "read the code" to "check the mapping".
Exception: `custom_transform` blocks in mappings may contain agent-written SQL, always flagged
for line-by-line human review.

**ADR-3: Silver = hub/link/satellite on canonical business entities.**
Rationale: stability under source churn (per doc 06); SCD2 by construction; brutally repetitive
loading pattern is ideal for codegen. Consequence: silver is join-heavy; only gold is queried
by consumers.

**ADR-4: Demand-pull tiering.**
Tier 1 canonical (~50–200 entities), Tier 2 conformed reference, Tier 3 conformed silver
(source-shaped tables in `<org>_silver.conformed`; bronze stays strictly raw).
Rationale: modeling 10,000s of tables upfront is impossible with available staff and mostly
worthless. Promotion is a defined runbook (R5).

**ADR-5: Catalog per org × layer; shared masters in `ref_master`.**
Rationale: information barriers between public markets / private markets / PE enforced at grant
level; shared instrument/party identity avoids N parallel security masters (doc 05).

**ADR-6: Controller = Delta state table + Databricks Jobs, not an external orchestrator.**
Rationale: stays in the Databricks domain, one less platform; state is queryable/auditable SQL.
Revisit if cross-platform orchestration needs emerge.

**ADR-7: Graduated autonomy with proposer/critic separation.**
Human gates are not removed; they are converted to policies. A decision type moves L0 → L1 → L2
only on measured agreement statistics, with random audit samples, automatic demotion triggers,
and design-authority + Risk sign-off. Entity model changes, grants, intake confirmation, and
high-blast-radius merges are never automated. Full matrix in doc 09 §4.

**ADR-8: Draft-by-agent, edit-by-human — no blank pages.**
The objective is eliminating human-typed code and minimizing human-typed text, not reducing
headcount. Every artifact starts as an agent draft (A1 pre-fills intakes, A3 drafts mappings,
A10 drafts entity and use-case specs and skill edits, Claude Code drafts platform code); humans
contribute judgment as edits and approvals. Enforcement: CI rejects any `edw-pipelines` commit
whose files lack a valid renderer provenance hash (doc 04 §4) — hand-written pipeline code
cannot merge. Exception: business meaning in intake prose is human-written ground truth;
agent-fabricated plausible semantics rubber-stamped by a reviewer is the failure mode to avoid.
North-star metrics: human-authored lines merged per repo, edit distance on agent drafts (doc 09 §7).
