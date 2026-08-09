# 03 — Agents and Skills

## 1. Anatomy of an agent

Every agent is the same three-part construction, differing only in configuration:

```
Agent = Runner (Python job) + Skills (versioned prompt packages) + Tools (scoped functions)
```

- **Runner** — a Python application run as a Databricks Job. Loads the skill, gathers inputs,
  calls the model endpoint with structured-output enforcement (pydantic schema), retries on
  schema violation (max 3), writes every prompt/response/decision to `edw_meta.agent_audit`.
  One shared runner framework in `edw-agent-factory`; agents are configuration.
- **Skill** — a directory in `edw-agent-factory/skills/<name>/` containing `SKILL.md`
  (instructions, rules, worked examples), few-shot examples, and the pydantic/JSON schema of the
  required output. Skills are versioned; the audit log records which skill version produced which
  artifact. Prompt improvements = PRs to skills, testable against a golden set (§4).
- **Tools** — the only capabilities the model can invoke. No general code execution, no
  unrestricted SQL. Tool implementations enforce scoping (org, row limits) *in code*, not in the
  prompt.

### Shared tool library

| Tool | What it does | Guardrails |
|---|---|---|
| `get_uc_metadata(table)` | Schema, comments, tags, lineage from UC | Read-only, org-scoped SP |
| `sample_rows(table, n)` | Sampled rows | ≤1,000 rows, masked columns stay masked, org-scoped |
| `run_profile(table)` | Invokes deterministic profiling engine | Aggregates only returned to model |
| `read_spec(path)` / `propose_spec(path, content)` | Read specs; write = branch + PR only | Never direct commit to main |
| `file_issue(repo, body)` | Opens tracker issue | — |
| `query_sandbox(sql)` | SQL against dev sandbox catalog only | Validator agent only |
| `search_entities(text)` | Semantic search over entity specs + existing mappings | Read-only |

## 2. Agent specifications

### A1 — Profiler
- **Trigger:** state `REGISTERED`, or Sentinel drift event.
- **Input:** bronze table(s) of one source feed.
- **Process:** calls `run_profile` (deterministic), then LLM interprets: proposes grain, candidate
  business keys with confidence, drafts column descriptions, flags PII-shaped columns, drafts a
  pre-filled `intake.md` for the steward.
- **Output:** `discovery.yml` (spec PR), pre-filled `intake.md`.
- **Skill:** `profiling-interpretation`. **Model:** mid-tier (high volume, structured task).
- **Guardrails:** cannot mark anything as confirmed; everything it writes is `provenance: agent`.

### A2 — Contract Compiler
- **Trigger:** state `INTAKE_CONFIRMED`, or drift-driven recompile.
- **Input:** `intake.md` + `discovery.yml`.
- **Process:** field-by-field merge under precedence rules — physical facts: discovered wins;
  semantics: human wins; contradictions (human grain vs observed duplicates, human "not sensitive"
  vs PII scan hit, declared key with nulls): **block and file issue**, never guess.
- **Output:** `contract.yml` + version bump + PR; or `COMPILE_BLOCKED` issue.
- **Skill:** `contract-authoring`. **Model:** mid-tier.
- **Guardrails:** output must pass JSON Schema in-loop before PR; cannot modify `human` fields.

### A3 — Entity Mapper (the judgment agent)
- **Trigger:** state `CONTRACTED`.
- **Input:** `contract.yml`, entity catalog (`search_entities`), tiering rules, existing mappings
  of the same source system (consistency).
- **Process:** (1) Tier classification with rationale — consumption signals, entity overlap,
  steward intent. (2) For Tier 1: propose `mapping.yml` per target entity — business-key
  derivation, column→attribute mapping with confidence scores, dedup rule, `custom_transform`
  SQL only where a template cannot express the transform. (3) For Tier 3: emit conformed-silver
  mapping (rename/type/dedup only, target `<org>_silver.conformed`).
- **Output:** tier decision + `mapping.yml` PR. **Human gate: modeler approves.** Low-confidence
  mappings (<0.8) are listed at top of PR description for reviewer attention.
- **Skill:** `entity-mapping`. **Model:** top-tier (this is where quality pays).
- **Guardrails:** cannot create new entities — may only file an `entity-proposal` issue for the
  design authority; cannot self-approve.

### A4 — Codegen
- **Trigger:** mapping approved.
- **Process:** deterministic Jinja rendering of `mapping.yml` through templates (doc 06): bronze
  ingestion, hub/key-map upsert, satellite MERGE, link load, conformed-silver, DLT expectations
  from contract checks, pytest unit tests with synthetic fixtures derived from the contract.
  The LLM's only role: generate fixture edge cases and PR description; it does not write pipeline
  code. `custom_transform` blocks pass through verbatim, flagged `REVIEW REQUIRED`.
- **Output:** branch in `edw-pipelines` (bundle for org × domain).
- **Skill:** `codegen-review` (self-check pass). **Model:** mid-tier.

### A5 — Gold Projector
- **Trigger:** new/changed `use-case.md`.
- **Process:** reads use-case spec (required entities, grain, filters, consumer group, freshness),
  generates gold views/materialized views over silver current-views, generates `GRANT` statements
  for the consumer group, refuses (files issue) if the use case needs unmapped Tier-3 data →
  triggers promotion runbook R5.
- **Output:** PR with views + grants. **Model:** mid-tier.
- **Guardrails:** may only read silver canonical + conformed; never bronze. Grants only to the
  group named in the spec, only within the org's gold catalog.

### A6 — Validator
- **Trigger:** A4/A5 branch ready.
- **Process:** deploys bundle to `<org>_dev` sandbox; runs pipeline on profiled sample data;
  checks: output schema ≡ entity spec, key uniqueness, row-count reconciliation
  (source vs hub+sat within dedup tolerance), SCD2 integrity (no overlapping effective ranges),
  all expectations fire correctly on seeded bad rows. LLM writes the human-readable verdict and,
  on failure, a structured defect report back to A4. Max 3 fix loops → escalate to engineer.
- **Output:** validation report attached to PR (merge is blocked without a green report).
- **Skill:** `validation-review`. **Model:** mid-tier.

### A8 — Reviewer (the critic that earns autonomy)
- **Trigger:** every A3 mapping proposal (runs before or alongside human review per autonomy level).
- **Input:** `mapping.yml`, `contract.yml`, entity spec, sample data, all existing mappings of
  the same source system.
- **Process:** independent verification — deliberately a *different skill and prompt* from A3
  (proposer/critic separation): entity choice sanity, business-key logic vs observed duplicate
  rates, cross-source mapping consistency, semantic plausibility per column, completeness
  (unmapped columns justified). Emits verdict: `concur` | `disagree(reasons)` | `escalate`.
- **Output:** structured review posted to the mapping PR; verdict logged to `agent_audit` for
  agreement statistics (doc 09 §4). At L1+, `concur` + policy conditions = auto-approval.
- **Skill:** `mapping-critique`. **Model:** top-tier.
- **Guardrails:** cannot edit the mapping (critic never becomes co-author); `custom_transform`,
  `ref_master` entities, and tier promotions always escalate to a human modeler.

### A9 — Operator (runbooks as playbooks)
- **Trigger:** Sentinel-classified events mapped to runbooks R2 (minor), R3, R4.
- **Process:** executes the runbook as a step-wise playbook; every verification gate in the
  runbook (A6 reconciliation, quarantine classification, expectation replay) is a hard stop —
  failure pages the ops engineer with full context. Approval points per the doc 09 §4 matrix
  (e.g. R4 atomic swap requires an ops-engineer click until that step reaches L1).
- **Output:** executed playbook log in `edw_meta.agent_audit`; PR/issue paperwork as the runbook
  requires.
- **Skill:** one per playbook (`playbook-r2-minor`, `playbook-r3`, `playbook-r4`). **Model:** mid-tier.
- **Guardrails:** can only act inside a playbook definition; anything unrecognized → page human
  (novel incidents are never agent-handled); no access to grants, entity specs, or `ref_master`.

### A10 — Drafter (kills the blank page, ADR-8)
- **Trigger:** on demand (modeler starting an entity; consumer team starting a use case) or
  monthly (skill-edit proposals from harvested corrections).
- **Process:** three drafting modes, one skill each:
  (1) *Entity specs* — reads all discovery profiles touching a domain, vendor data dictionaries,
  and existing entity specs; drafts `entity.md` including candidate attributes, key definition,
  and precedence questions for the modeler, with open questions explicitly marked `TODO(human)`.
  (2) *Use-case specs* — conducts a structured interview with the consumer team (questions this
  must answer, entities, grain, freshness, restrictions); drafts `use-case.md` from the transcript.
  (3) *Skill edits* — analyzes the month's harvested human corrections (R7) and proposes concrete
  prompt/example diffs to the affected skills.
- **Output:** draft PRs only. **Every A10 output is L0 permanently** — drafts are edited and
  merged by modelers (entity), consumer team + steward (use case), platform engineers (skills).
- **Skills:** `entity-drafting`, `use-case-interview`, `skill-refinement`. **Model:** top-tier.
- **Guardrails:** may never invent business meaning silently — anything not grounded in a
  profile, dictionary, or interview answer must be marked `TODO(human)`; drafts with unresolved
  TODOs cannot merge (CI check).

### A7 — Sentinel
- **Trigger:** continuous (scheduled + event-driven from DLT expectation metrics).
- **Process:** consumes drift-detector diffs, expectation failure rates, freshness vs contract SLA.
  Classifies severity, maps to change class (doc 02 §4), opens the right artifact: auto
  version-bump PR (minor), issue + runbook link (major), or incident (R3).
- **Output:** issues, PRs, alerts. **Model:** small/mid-tier.
- **Guardrails:** never restarts or modifies production pipelines; alerting and paperwork only.

## 3. Chaining — who calls whom

Agents never call each other directly. All chaining goes through the **state controller**
(doc 04) reading `edw_meta.onboarding_state`, and through **git events** (PR merged → state
advance). This makes the chain restartable, auditable, and lets humans intervene at any state by
editing the state row or the PR. An agent crash = job retry; a poisoned artifact = revert the PR.

## 4. Skill quality loop

`edw-agent-factory/goldens/` holds golden cases per skill: real (anonymized) inputs + approved
outputs. CI replays goldens on every skill change and reports diffs — prompt engineering with
regression tests. Every human correction to an agent PR is harvested monthly into new goldens
(ops manual R7), so the system learns from review without any model fine-tuning.

For A8/A9 the golden sets carry extra weight: agreement between A8's verdicts and human
decisions is the statistic that promotes a decision type through autonomy levels (doc 09 §4),
and any skill/model version change automatically demotes the affected decision type one level
until goldens replay clean and a 50-decision re-qualification passes.

The harvest loop itself follows ADR-8: A10's `skill-refinement` mode drafts the skill edits from
the month's corrections; platform engineers review the diff and the golden replay, then merge.
Humans stop writing prompts the same way they stopped writing pipelines — they review them.
