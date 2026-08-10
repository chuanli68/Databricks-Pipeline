# Enterprise Data Warehouse on Databricks
## Consolidated Design Document

**Version:** 0.9 (draft for review) · **Date:** 2026-08-10 · **Status:** open for comment

---

## About this document

### Who it is for

| Reader | Suggested path |
|---|---|
| **Technology leadership** | Chapters 1, 3, 10, 13, 14 — problem, architecture, plan, decisions, open questions |
| **Architects** | All chapters; chapters 3, 6, 7 carry the structural decisions |
| **Data modellers** | Chapters 2, 4, 8 — modelling method, specification system, physical standards |
| **Developers / platform engineers** | Chapters 4, 5, 6, 8, 11, 12 — specs, agents, pipelines, operations, prototype |
| **Governance and risk** | Chapters 7, 9, 13, 14 — access control, autonomy and accountability, open questions |

Chapters 1–2 assume no data-warehousing background. Later chapters get progressively more
technical. Every acronym is defined in [Appendix A](#appendix-a--glossary); every external
standard or vendor feature relied on is cited in [Appendix B](#appendix-b--references).

### Status labels — used throughout

The design is not uniformly mature, and this document says so explicitly rather than presenting
everything with equal confidence.

| Label | Meaning | What feedback is useful |
|---|---|---|
| **`[SETTLED]`** | Decided; reversing it would restructure the design | Challenge only with new evidence — but do challenge |
| **`[WORKING]`** | Current answer, reasonable confidence, still soft | Alternatives and refinements welcome |
| **`[OPEN]`** | Genuinely unresolved; needs a decision or an owner | Answers, opinions, and volunteers all welcome |
| **`[PARKED]`** | Deliberately deferred; not forgotten | Tell us if you think it can't wait |
| **`[SUPERSEDED]`** | Replaced by a later decision; kept for the record | — |

Each chapter opens with a status box summarising its maturity and naming what feedback would be
most valuable.

### How to give feedback

Comment inline, or raise an issue against the relevant chapter and decision identifier
(for example "Ch 8 / ADR-3" or "Q3"). The consolidated decision register is
[Chapter 13](#chapter-13--decision-register); the open-questions queue is
[Chapter 14](#chapter-14--open-questions-and-feedback-register). Both are the intended
landing points for disagreement.

### Source documents

This document consolidates and supersedes, for reading purposes, the working documents
`docs/00`–`docs/09`. Those remain the maintained sources; where this document and a source
document disagree, the source document is correct and this one needs updating.

### Maturity summary

| Chapter | Subject | Overall status |
|---|---|---|
| 1 | Problem and constraints | `[SETTLED]` |
| 2 | Industry foundations | `[SETTLED]` |
| 3 | Architecture and decision records | `[SETTLED]` core, `[WORKING]` edges |
| 4 | Specification system | `[WORKING]` |
| 5 | Agents and skills | `[WORKING]` — none built yet |
| 6 | Orchestration and delivery | `[WORKING]`, one `[OPEN]` (orchestrator choice) |
| 7 | Catalogs and access control | `[WORKING]`, one `[OPEN]` (cross-org identity) |
| 8 | Silver standards and code generation | `[SETTLED]` model, `[OPEN]` implementation mechanism |
| 9 | Team and graduated autonomy | `[WORKING]` — unvalidated hypothesis |
| 10 | Implementation plan | `[WORKING]` |
| 11 | Operations | `[WORKING]` |
| 12 | Prototype and evidence | `[SETTLED]` for what it covers |

---

# Chapter 1 — Problem and constraints

> **Status:** `[SETTLED]` — the constraints are given, not chosen.
> **Feedback wanted:** is any constraint stated too strongly or too weakly? Constraint 4 in
> particular drives the entire design; if it is negotiable, much of this document changes.

## 1.1 What we are building

An enterprise data warehouse on Databricks, organised with the **medallion architecture** — the
three-layer pattern Databricks recommends, in which data progresses through Bronze (raw), Silver
(validated and modelled) and Gold (business-ready) layers, improving in structure and quality at
each step [[1]](#r1).

## 1.2 The four constraints

**1. Scale of inputs.** Tens of thousands of source tables from many internal systems and
external vendors, whose schemas change without notice or coordination.

**2. Organisational segregation.** Data is separated by organisation — public markets, private
markets, private equity. Information barriers between them are a control requirement, not a
preference or a convenience.

**3. Insufficient specialist staff.** There are not enough data modellers or engineers to
hand-build this, now or in any realistic future. Hiring to the size of the problem is not an
available option.

**4. Stability under change — the hard requirement.** A change to an input source must not
trigger a rebuild or reload of everything downstream. A vendor adding a column must not cost a
weekend of engineering.

## 1.3 Why the conventional approach does not fit

Most enterprise warehouses are stable *in practice* because a team of engineers quietly absorbs
the churn: a vendor restructures a feed, and someone spends two days rewriting a load and
backfilling a dimension. That model does not survive constraint 3, and at the scale of constraint
1 it does not survive at all.

So stability has to come from the architecture rather than from labour. This document is
principally an answer to the question: **what shape must a warehouse have, such that a change in
one source cannot propagate beyond a bounded, predictable blast radius — and such that most of the
work of building and maintaining it can be automated?**

## 1.4 The originating idea

The seed proposal was: give every Bronze input a clear written description, define how the data
should be used and what the target schema should be, and let AI agents transform it forward
through the layers. That instinct was sound. The work since has been making it precise enough to
execute — which specifications, owned by whom, validated how, consumed by what.

---

# Chapter 2 — Industry foundations

> **Status:** `[SETTLED]` — this chapter is background, not invention.
> **Feedback wanted:** if you know these methods well, is the characterisation fair? In particular,
> is the Data Vault critique in §2.2 the one practitioners would make?

Readers already familiar with dimensional modelling and Data Vault may skip to Chapter 3.

## 2.1 Dimensional modelling (Kimball)

The classical warehouse pattern [[6]](#r6): **facts** (measurements — a trade, a valuation)
surrounded by **dimensions** (descriptive context — the instrument, the portfolio, the date),
arranged for fast and comprehensible querying.

Its answer to "an attribute changed and I need to know what it used to be" is the **Slowly
Changing Dimension (SCD)**. The common form, **Type 2**, does not overwrite a changed value:
it closes the existing row by stamping an end date on it, and inserts a new row carrying the new
value. The table therefore holds the full history of what was true at any point in time.

Dimensional modelling is excellent for consumption and weak at absorbing source churn — a
restructured source generally means a restructured dimension, and dimensions are what everything
downstream depends on.

## 2.2 Data Vault 2.0 (Linstedt)

A modelling method built specifically for many volatile sources feeding one warehouse
[[5]](#r5). It decomposes the model into three table types:

- **Hub** — the business key of an entity and nothing else. One row per real-world thing.
- **Link** — a relationship between hubs.
- **Satellite** — descriptive attributes for a hub or link, **one satellite per source system**,
  with effective dating built in.

The design intent is a **stable core (hubs) with flexible edges (satellites)** that is resilient
to environmental change — which is precisely constraint 4. Databricks publishes prescriptive
guidance for implementing Data Vault on the lakehouse [[3]](#r3) and positions it alongside
dimensional modelling as a supported approach [[4]](#r4).

The standard criticisms are fair and worth stating plainly: Data Vault is **verbose to build**
(many small tables, much repetitive loading logic) and **unfriendly to query** (many joins to
reassemble a business view). Both objections matter less here, for reasons given in §3.4 and
§3.5 — in short, a machine writes the verbose part, and nobody queries the layer directly.

## 2.3 Where this design sits

**Silver is Data Vault; Gold is dimensional.** The stable, source-absorbing layer uses hubs,
links and satellites. The consumption layer projects that into the friendly shapes analysts
expect. This combination is described in Databricks' own modelling guidance as a normal lakehouse
pattern [[4]](#r4), and it matches the medallion layer definitions directly: Silver is where
cleansing, deduplication and normalisation belong; Gold is where dimensional modelling and
aggregation belong [[1]](#r1).

---

# Chapter 3 — Architecture

> **Status:** `[SETTLED]` for the eight architecture decision records; `[WORKING]` for component
> details. One decision (ADR-6, orchestration) is explicitly soft.
> **Feedback wanted:** ADR-2 and ADR-3 are the load-bearing choices. If either is wrong, most of
> the rest follows it down — challenge them first.

## 3.1 The six load-bearing ideas

Everything else in this document is downstream of these.

### 3.1.1 Agents run at build time, never at runtime — `[SETTLED]`

AI agents read specifications, generate mappings and code, and open pull requests for human
review. The production pipelines that actually move data are ordinary, reviewed, deterministic
code with no language model anywhere in the data path.

*Rationale:* determinism, auditability, cost, and the ability to explain any number in the
warehouse without recourse to "the model decided". *Consequence:* an agent failure is a failed
pull request, never corrupted data.

### 3.1.2 Language models emit specifications; templates emit code — `[SETTLED]`

The model's output is structured YAML — a source contract, a mapping. Deterministic **Jinja**
templates (a standard Python templating engine — mail-merge for code) render that YAML into
pipeline code.

*Why this is the load-bearing idea:*

- Review becomes tractable at scale: a reviewer checks a 30-line mapping, not 300 lines of SQL.
- Generated code is uniform across thousands of pipelines because they share one template.
- A template fix becomes a fleet-wide upgrade by regenerating from unchanged mappings.
- It eliminates the failure mode where a model invents a novel code shape that works but which
  nobody recognises a year later.

*Cost:* anything a template cannot express needs a `custom_transform` escape hatch containing
hand-reviewed SQL. That surface must stay small; if it grows, the template library is what needs
fixing.

### 3.1.3 Silver is modelled on the business domain — `[SETTLED]`

Not on sources (they churn) and not on use cases (they multiply). What has not changed in decades
is what a Position, an Instrument or a Fund actually *is*.

The software-architecture analogy is **hexagonal architecture**, also called ports-and-adapters
[[7]](#r7): the domain model sits at the centre, every external system is an adapter around it,
and adapters never dictate the domain's shape. Silver is the domain layer; every source system is
an adapter.

### 3.1.4 Identity is separated from attributes — `[SETTLED]`

Hubs hold identity; satellites hold attributes; a key map resolves each source system's identifier
to the enterprise one (the security-master pattern, generalised to every entity).

*The passport analogy:* the hub is the passport number — permanent identity. Satellites are the
stamps each country adds. New country, new stamps; nobody reissues the passport.

Three properties follow, and together they are the answer to constraint 4:

- **History comes for free.** A satellite *is* a Slowly Changing Dimension Type 2 table by
  construction. There is no per-table history design decision left to get wrong.
- **Bounded blast radius.** Any source change touches one mapping and one satellite. A vendor
  replacement means a new satellite while the old is frozen but still queryable. No change class
  in this design triggers a warehouse-wide reload.
- **Ideal for code generation.** Satellite loading is the same merge, hash-comparison and
  effective-dating logic thousands of times over, differing only in column lists. That tedium is
  the usual human objection to Data Vault and precisely why a machine should do it.

*Accepted trade-off:* Silver is join-heavy and unpleasant to query directly. Nobody queries
Silver. Gold projects it into friendly shapes, and Gold is cheap, regenerable views.

### 3.1.5 Demand-pull tiering — `[SETTLED]`

Modelling 30,000 tables upfront is impossible with the available staff and mostly worthless, as
most will never be queried.

| Tier | Treatment | Approximate volume |
|---|---|---|
| **Tier 1** | Full canonical modelling: hub, key map, satellites, links | ~50–200 entities |
| **Tier 2** | Reference data, lightly conformed | Modest |
| **Tier 3** | *Conformed Silver*: typed, renamed, deduplicated, still source-shaped | The long tail |

Tier 3 is promoted into the canonical model only when a Gold use case actually requires it
(runbook R5, Chapter 11).

### 3.1.6 Humans edit; agents draft and type — `[SETTLED]`

The goal is **not fewer people**. It is zero human-typed pipeline code and minimal human-typed
text. Every artifact starts as an agent draft; humans contribute judgment as edits and approvals.
Approval gates are converted into measured policies, not removed.

Permanently human by design: business meaning (grain, definitions, quirks — ground truth an agent
would otherwise plausibly fabricate), entity model changes, access grants, and incident command
for novel failures.

## 3.2 Component inventory

### 3.2.1 Repositories — the source of truth

| Repository | Contents | Written by | Reviewed by |
|---|---|---|---|
| `edw-specs` | Source contracts, entity specs, mapping specs, use-case specs, tiering decisions | Agents (via pull request) and stewards | Stewards, modellers |
| `edw-pipelines` | Generated pipeline code, tests, deployment bundles — one bundle per organisation × domain | Code-generation agent | Data engineers |
| `edw-agent-factory` | Agent runner framework, skills, code templates, validators, schemas | Platform team | Platform team |

### 3.2.2 Agents — build time only

| ID | Agent | Consumes | Produces |
|---|---|---|---|
| A1 | Profiler | Bronze table (sampled), catalog metadata | Discovery snapshot, pre-filled intake form |
| A2 | Contract Compiler | Intake form + discovery snapshot | Versioned source contract, or a blocking conflict |
| A3 | Entity Mapper | Contract, entity catalog | Tier decision and mapping proposal |
| A4 | Code Generator | Approved mapping, templates | Pipeline code, tests, quality expectations |
| A5 | Gold Projector | Use-case spec, Silver model | Gold views and access grants |
| A6 | Validator | Generated code, sandbox | Validation report; iterates with A4 |
| A7 | Sentinel | Quality events, schema drift, freshness | Issues, version-bump pull requests |
| A8 | Reviewer | A3's mapping proposals | Independent critic verdict; enables auto-approval |
| A9 | Operator | Runbook triggers | Playbook execution with verification gates |
| A10 | Drafter | Profiles, dictionaries, interviews, harvested corrections | Draft entity and use-case specs, proposed skill edits |

Full specifications in [Chapter 5](#chapter-5--agents-and-skills).

### 3.2.3 Deterministic services — no language model involved

| Service | Implementation | Purpose |
|---|---|---|
| Profiling engine | PySpark job | Row counts, null rates, cardinality, candidate keys, distributions, PII pattern scan. A1 only *interprets* its output |
| Specification validator | JSON Schema + pydantic, in CI | Rejects malformed specs before any agent or human sees them |
| Code renderer | Jinja2 | Mapping → SQL/PySpark. Same mapping in, byte-identical code out |
| CI/CD | GitHub Actions + Databricks Asset Bundles | Validate → test → deploy dev → integration-test → deploy production |
| Drift detector | Scheduled job | Diffs live source schema against the contract; feeds A7 |
| Catalog sync | Scheduled job | Pushes contract descriptions and tags into Unity Catalog; flags divergence |
| State controller | Databricks Job | Advances the onboarding state machine (Chapter 6) |

### 3.2.4 Platform components

- **Unity Catalog** — governance backbone: catalogs per organisation × layer, grants, lineage,
  tags, column masks and row filters (Chapter 7).
- **Lakeflow Declarative Pipelines** — Bronze→Silver runtime code, with data-quality expectations
  as the safety net.
- **Auto Loader / Lakeflow Connect** — Bronze ingestion from databases and feeds.
- **Databricks Jobs** — agent runners, profiler, controller, sentinel, sync jobs.
- **Databricks Asset Bundles** — packaging and promotion across dev/test/production.
- **`edw_meta` catalog** — operational state: onboarding state, profiling results, validation
  reports, agent audit log, run ledger.
- **Model access** — Claude via Databricks Mosaic AI external models: a governed, logged endpoint
  with no data egress. Direct vendor API calls from jobs are avoided. `[OPEN]` — pending
  model-governance approval (Q5).

## 3.3 End-to-end flow — onboarding one source

1. Steward registers the source. State: `REGISTERED`.
2. **A1 Profiler** runs the profiling engine and drafts a discovery snapshot plus a pre-filled
   intake form. State: `DISCOVERED`.
3. **Steward confirms the intake form** — a ten-minute review of a pre-filled document, not a
   blank one. State: `INTAKE_CONFIRMED`.
4. **A2 Contract Compiler** merges human intent with machine facts into a versioned contract.
   Contradictions block with an issue rather than being guessed. State: `CONTRACTED`.
5. **A3 Entity Mapper** classifies the tier and proposes a mapping. **A8 Reviewer** critiques it
   independently. **Human gate: modeller approves.** State: `MAPPED`.
6. **A4 Code Generator** renders pipeline code, tests and expectations. **A6 Validator** deploys
   to a sandbox, runs on sampled data, checks schema, keys and reconciliation; loops with A4 up to
   three times, then escalates. State: `VALIDATED`.
7. Pull request to `edw-pipelines`. **Human gate: engineer merges.** CI deploys.
   State: `DEPLOYED` → `LIVE`.
8. **A7 Sentinel** monitors indefinitely; drift and quality events re-enter the flow at the
   appropriate step, scoped by change class.

**Three human touch points per feed** — intake confirmation (steward), mapping approval
(modeller), merge (engineer). Under graduated autonomy (Chapter 9), gates two and three are
progressively delegated to policy, leaving intake confirmation as the only permanent one.

## 3.4 Architecture decision records

| ADR | Decision | Status | Rationale | Consequence |
|---|---|---|---|---|
| **ADR-1** | Agents operate at build time only | `[SETTLED]` | Determinism, auditability, regulatory expectations, cost | Runtime incidents are ordinary pipeline incidents; agents cannot corrupt data |
| **ADR-2** | Model output is specifications (YAML), not free-form code | `[SETTLED]` | Schema-validatable; uniform generated code; review shrinks to checking a mapping | Escape hatch (`custom_transform`) needed and must stay small |
| **ADR-3** | Silver is hub/link/satellite over canonical business entities | `[SETTLED]` | Stability under source churn; history by construction; repetition suits generation | Silver is join-heavy; only Gold is queried |
| **ADR-4** | Demand-pull tiering | `[SETTLED]` | Modelling the whole estate is infeasible and mostly wasted | Long tail stays source-shaped until needed; promotion is a defined runbook |
| **ADR-5** | Catalog per organisation × layer; shared masters in `ref_master` | `[WORKING]` | Information barriers enforced by grants; avoids N parallel security masters | Depends on Q3 — governance must accept shared identity |
| **ADR-6** | Controller is a state table plus Databricks Jobs, not an external orchestrator | `[WORKING]` | One less platform; state is queryable, auditable SQL | Revisit if an enterprise orchestrator is mandated (Q4) |
| **ADR-7** | Graduated autonomy with proposer/critic separation | `[WORKING]` | Gates become measured policies rather than being removed | Requires agreement statistics before any promotion; unvalidated until Phase 2 |
| **ADR-8** | Draft-by-agent, edit-by-human — no blank pages | `[SETTLED]` | Objective is eliminating human-typed code, not headcount | CI rejects hand-written pipeline code via renderer provenance hash |

---

# Chapter 4 — The specification system

> **Status:** `[WORKING]` — the six artifacts are stable in concept; field-level detail will move
> once real sources are onboarded.
> **Feedback wanted:** is the human/agent ownership split in §4.3 right? It is the mechanism that
> prevents agents from fabricating business meaning.

Specifications are the interface between humans, agents and code generation. Every specification
is a file in `edw-specs`, schema-validated in continuous integration, semantically versioned, and
merged only through pull request.

## 4.1 The six artifacts

| # | Artifact | File | Authored by | Consumed by | Volatility |
|---|---|---|---|---|---|
| S1 | Human intake | `intake.md` | Steward (pre-filled by A1) | A2 | Low |
| S2 | Discovery snapshot | `discovery.yml` | A1 (engine + interpretation) | A2, A7 | Regenerated on drift |
| S3 | Source contract | `contract.yml` | A2 (compiled) | A3, A4, A7, catalog sync | Version-managed |
| S4 | Entity specification | `entity.md` | A10 draft, modeller-edited | A3, A4, A5 | **Very low — the stable core** |
| S5 | Mapping specification | `mapping.yml` | A3 (approved by modeller or policy) | A4 renderer | Medium — absorbs source change |
| S6 | Use-case specification | `use-case.md` | A10 interview draft, consumer-edited | A5 | Per use case |

Templates for all six are in `templates/`.

## 4.2 Repository layout

```
edw-specs/
├── orgs/
│   ├── public_markets/
│   │   ├── sources/<source_system>/<feed>/
│   │   │   ├── intake.md
│   │   │   ├── discovery.yml         # regenerated; committed for audit
│   │   │   ├── contract.yml          # canonical, versioned
│   │   │   └── mappings/<entity>.yml # one per target entity
│   │   └── use-cases/<name>/use-case.md
│   ├── private_markets/ …
│   └── private_equity/ …
├── entities/                         # canonical model, shared across organisations
│   ├── instrument.md, party.md, portfolio.md, position.md,
│   ├── transaction.md, valuation.md
│   └── pe/{fund.md, deal.md, portfolio_company.md}
├── schemas/                          # JSON Schemas validating everything above
└── tiering/tier-decisions.yml        # one line per source table
```

Entity specifications sit **outside** the organisation directories deliberately: instrument and
party identity is shared, and the physical hubs live in a shared catalog (Chapter 7).
Organisation-specific entities may live under `entities/<org>/`.

## 4.3 Provenance — who owns which field — `[SETTLED]`

This is the mechanism that stops agents inventing business meaning.

| Provenance | Meaning | Rules |
|---|---|---|
| `human` | Undiscoverable: grain, definitions, sensitivity, service levels | **No agent may ever modify these.** An agent may only open an issue proposing a change |
| `discovered` | Observable: types, null rates, cardinality, candidate keys | Drift automation may auto-update these via a version-bump pull request |
| `agent` | Inferred: proposed descriptions, proposed checks | The fields reviewers should concentrate on |
| `agent_human_approved` | Agent-proposed, human-confirmed | Treated as human thereafter |

**The compiler blocks on contradiction.** If the steward declares a grain of one row per
instrument per day and profiling finds duplicates on that key, A2 emits no contract — it files a
conflict and stops. Likewise if a column marked non-sensitive contains identifier-shaped values.
Guessing here would poison everything downstream, and quietly.

## 4.4 Versioning and change classes — `[WORKING]`

Contracts and entity specifications are versioned semantically; the version determines what
regenerates.

| Change | Version bump | Downstream effect | Reload? |
|---|---|---|---|
| Description or documentation only | patch | Catalog sync only | No |
| New column in source | minor | Bronze and affected satellite evolve additively | No |
| Column type widened | minor | Satellite column evolves | No |
| Type narrowed, column dropped or renamed | major | New satellite version; old frozen but queryable | No |
| Business key or grain change | major | **Human-led** — treated as a new source generation (runbook R6) | New satellite only |
| Entity specification change | major, design authority only | Modeller-led; affected mappings re-proposed | No |

**The invariant behind every row:** hubs, links, and other sources' satellites are never touched.
There is no change class in this table that triggers a warehouse reload.

## 4.5 Specification lifecycle

```
DRAFT → VALIDATED (schema check in CI) → PROPOSED (pull request open) → ACTIVE (merged)
ACTIVE → SUPERSEDED (newer version merged) → RETIRED (source decommissioned)
Conflict at compile time → COMPILE_BLOCKED + issue; no contract is emitted
```

## 4.6 Specifications and the catalog stay in sync

A deterministic synchronisation job projects contracts into Unity Catalog so specifications are
not a side-car artifact: column descriptions become catalog comments (searchable, and consumed by
natural-language query tools); classification, service level, owner and tier become catalog tags.
The reverse check matters too — if someone edits a catalog comment by hand, the job flags the
divergence and opens an issue. Git remains the source of truth.

---

# Chapter 5 — Agents and skills

> **Status:** `[WORKING]` — the architecture is specified; **not one agent has been built**.
> Every claim about agent quality in this chapter is a hypothesis with a measurement plan
> attached, not a result.
> **Feedback wanted:** are the guardrails in §5.3 sufficient? Specifically A3, which is the only
> agent making genuine modelling judgments.

## 5.1 Anatomy — every agent is the same three parts

```
Agent = Runner (a Python job) + Skill (a versioned prompt package) + Tools (scoped functions)
```

- **Runner** — a Python application executed as a Databricks Job. It loads the skill, gathers
  inputs, calls the model endpoint with structured-output enforcement, retries on schema violation
  (maximum three), and writes every prompt, response and decision to `edw_meta.agent_audit`.
  There is one shared runner framework; individual agents are configuration, not code.
- **Skill** — a directory containing instructions, worked examples, and the schema of the required
  output. Skills are versioned, and the audit log records which skill version produced which
  artifact. Improving a prompt is therefore a reviewable pull request, testable against a golden
  set (§5.4).
- **Tools** — the only capabilities a model can invoke. No general code execution, no unrestricted
  SQL. Scoping (organisation, row limits, masking) is enforced **in the tool implementation**, not
  requested in the prompt.

### Shared tool library

| Tool | Purpose | Guardrail |
|---|---|---|
| `get_uc_metadata(table)` | Schema, comments, tags, lineage | Read-only, organisation-scoped identity |
| `sample_rows(table, n)` | Sample rows | ≤1,000 rows; masked columns stay masked |
| `run_profile(table)` | Invoke the deterministic profiling engine | Only aggregates returned to the model |
| `read_spec` / `propose_spec` | Read specs; write via branch and pull request only | Never a direct commit to main |
| `file_issue(repo, body)` | Open a tracker issue | — |
| `query_sandbox(sql)` | SQL against the development sandbox only | Validator agent only |
| `search_entities(text)` | Search entity specs and existing mappings | Read-only |

## 5.2 Agent specifications

### A1 — Profiler
Runs the deterministic profiling engine, then interprets: proposes grain, candidate business keys
with confidence scores, drafts column descriptions, flags identifier-shaped columns, and produces
a **pre-filled intake form** for the steward.
*Model tier:* mid. *Guardrail:* cannot mark anything as confirmed; everything it writes carries
`provenance: agent`.

### A2 — Contract Compiler
Merges intake and discovery field by field under fixed precedence: physical facts — discovered
wins; semantics — human wins; contradictions — **block and file an issue, never guess**.
*Model tier:* mid. *Guardrail:* output must pass schema validation before a pull request opens;
cannot modify `human` fields.

### A3 — Entity Mapper — *the judgment agent*
Classifies the source into a tier with written rationale, and for Tier 1 proposes a mapping per
target entity: business-key derivation, column-to-attribute mapping with per-column confidence,
deduplication rule, and `custom_transform` SQL only where a template cannot express the transform.
Mappings scoring below 0.8 confidence are listed at the top of the pull request for reviewer
attention.
*Model tier:* top — this is where quality pays for itself. *Guardrails:* **cannot create new
entities** (may only file an entity proposal for the design authority); cannot self-approve.

### A4 — Code Generator
Renders the approved mapping through Jinja templates: ingestion, hub and key-map upsert, satellite
load, link load, conformed tables, quality expectations derived from contract checks, and unit
tests with synthetic fixtures. **The model does not write pipeline code** — its only contribution
is fixture edge cases and the pull-request description. `custom_transform` blocks pass through
verbatim, flagged `REVIEW REQUIRED`.

### A5 — Gold Projector
Generates Gold views and the corresponding access grants from a use-case specification. Refuses —
and files an issue — if the use case needs data that is still Tier 3, which triggers the promotion
runbook.
*Guardrails:* may read Silver only, never Bronze; may grant only to the group named in the
specification, only within that organisation's Gold catalog.

### A6 — Validator
Deploys the generated bundle to a sandbox and runs it against sampled data, checking: output
schema matches the entity specification; key uniqueness; row-count reconciliation between source
and target; history integrity (no overlapping effective ranges); and that expectations fire
correctly on deliberately seeded bad rows. Loops with A4 a maximum of three times before
escalating. **A green report is a required merge check.**

### A7 — Sentinel
Continuous monitoring: drift diffs, expectation failure rates, freshness against contracted
service levels. Classifies severity, maps it to a change class, and opens the appropriate artifact
— an automatic version-bump pull request for minor changes, an issue with a runbook link for major
ones.
*Guardrail:* never restarts or modifies production pipelines. Alerting and paperwork only.

### A8 — Reviewer — *the critic that earns autonomy*
An independent critique of every A3 mapping, deliberately using a **different skill and prompt**
from A3 (proposer/critic separation): entity choice, key logic against observed duplicate rates,
consistency with other mappings from the same source, semantic plausibility, and completeness.
Emits `concur`, `disagree(reasons)`, or `escalate`. Its agreement rate against human decisions is
the statistic that earns autonomy promotions (Chapter 9).
*Guardrail:* cannot edit the mapping — a critic must never become a co-author.

### A9 — Operator
Executes runbooks as step-wise playbooks with every verification gate as a hard stop; failure
pages an engineer with full context. Approval points follow the autonomy matrix.
*Guardrail:* can only act inside a defined playbook. Anything unrecognised pages a human — novel
incidents are never agent-handled.

### A10 — Drafter — *eliminates the blank page*
Three modes: drafting entity specifications from cross-source profiles and vendor dictionaries;
drafting use-case specifications from a structured interview with the consumer team; and proposing
skill edits from the month's harvested human corrections.
*Guardrail:* may never invent business meaning silently — anything not grounded in a profile,
dictionary or interview answer must be marked `TODO(human)`, and drafts with unresolved markers
cannot merge. **Permanently human-approved.**

## 5.3 How agents are chained

**Agents never call each other.** All chaining flows through the state controller (Chapter 6)
reading a state table, and through git events. This makes the chain restartable and auditable, and
lets a human intervene at any point by editing the state row or the pull request. An agent crash is
a job retry; a poisoned artifact is a reverted pull request.

## 5.4 Skill quality loop

A directory of **golden cases** per skill holds real (anonymised) inputs and approved outputs.
CI replays them on every skill change and reports differences — prompt engineering with regression
tests. Every human correction to an agent pull request is harvested monthly into new golden cases,
so the system improves from review without any model fine-tuning.

For A8 and A9 the golden sets carry additional weight: they gate autonomy promotions, and any
skill or model version change **automatically demotes** the affected decision type one level until
the goldens replay cleanly and a fifty-decision requalification passes.

---

# Chapter 6 — Orchestration and delivery

> **Status:** `[WORKING]`. ADR-6 (own controller versus enterprise orchestrator) is `[OPEN]` —
> see Q4. The approval-policy table in §6.3 is `[WORKING]` and needs risk sign-off.
> **Feedback wanted:** does the organisation mandate an orchestration platform? Answering that now
> is cheap; answering it in Phase 2 is not.

## 6.1 A state machine, not a pipeline graph

Source onboarding is long-running — days, because it contains human gates — so it cannot be a
single job graph. The unit of orchestration is **one state-machine row per source feed**. A
controller job runs every ten minutes (and on events), finds rows whose state has a runnable next
action, and launches the corresponding agent job.

```sql
CREATE TABLE edw_meta.onboarding_state (
  source_feed_id   STRING,     -- org.source_system.feed
  state            STRING,
  state_since      TIMESTAMP,
  awaiting         STRING,     -- NULL | steward | modeler | engineer | agent_retry
  contract_version STRING,
  active_pr        STRING,
  attempt          INT,
  last_error       STRING,
  updated_by       STRING      -- full history via change data feed
);
```

## 6.2 States and transitions

| State | Advanced by | Next |
|---|---|---|
| `REGISTERED` | Controller launches A1 | `DISCOVERED` |
| `DISCOVERED` | Steward confirms intake | `INTAKE_CONFIRMED` |
| `INTAKE_CONFIRMED` | Controller launches A2 | `CONTRACTED` or `COMPILE_BLOCKED` |
| `COMPILE_BLOCKED` | Human resolves the conflict | `INTAKE_CONFIRMED` |
| `CONTRACTED` | Controller launches A3; A8 reviews | `MAPPING_PROPOSED` |
| `MAPPING_PROPOSED` | Modeller approves — or policy auto-approves at L1+ | `MAPPED` |
| `MAPPED` | Controller runs A4→A6 loop | `VALIDATED` or `VALIDATION_FAILED` |
| `VALIDATION_FAILED` | Up to three retries, then an engineer | `MAPPED` |
| `VALIDATED` | Engineer merges — or policy auto-merges low-risk classes | `DEPLOYED` |
| `DEPLOYED` | First successful production run | `LIVE` |
| `LIVE` | Sentinel events | Re-enters at the appropriate state per change class |

Human gates are exactly the three `awaiting` values. A nightly digest per role lists everything
waiting on that person; anything waiting more than five business days surfaces in the weekly
operations review.

## 6.3 Approval and merge policy — `[WORKING]`

Enforced by a policy bot; the policy itself is versioned code.

| Risk class | Conditions for automation | L0 | L1 | L2 |
|---|---|---|---|---|
| Mapping, Tier 3 | A8 concurs | Modeller | Auto + 10% audit | Auto + 2–5% audit |
| Mapping, Tier 1 standard | All columns ≥0.8 confidence, A8 concurs, no custom SQL, not shared-identity | Modeller | Auto + 10% audit | Auto + 2–5% audit |
| Mapping, sensitive | Custom SQL, shared entity, tier promotion | Modeller | Modeller | Modeller |
| Merge, low-risk | Rendered-only diff, minor change, green validation, single target | Engineer | Auto + audit | Auto + audit |
| Merge, high-risk | Major change, custom SQL, template change, mass regeneration, grants | Engineer | Engineer | Engineer |

Autonomy levels are held per decision type per organisation and changed only with design authority
and Risk sign-off (Chapter 9).

## 6.4 Continuous integration and deployment

```
Pull request opened by A4 or A5
 ├─ renderer provenance check — every generated file carries a hash of
 │    (mapping version, template version, renderer version); CI recomputes it and
 │    REJECTS any file that was hand-edited (this is how ADR-8 is enforced)
 ├─ bundle validate
 ├─ unit tests with fixtures generated from the contract
 ├─ deploy to sandbox
 ├─ A6 integration validation — report posted to the pull request, required check
 └─ human review (engineer)
merge → deploy to test on full sample → tag → deploy to production
```

- **One deployment bundle per organisation × domain** — bounded blast radius, independent release
  cadence, clear ownership.
- The same generated code runs in every environment; only the target catalog is parameterised.
- Rollback is redeploying the previous bundle tag. Data rollback is per-satellite (runbook R4).

## 6.5 Environments

| Environment | Catalogs | Data | Users |
|---|---|---|---|
| Development | `<org>_dev` | Profiled samples, synthetic fixtures | Agents (A6), engineers |
| Test | `<org>_test_*` | Full copies of in-scope feeds | CI only |
| Production | `<org>_bronze/silver/gold` | Live | Runtime service principals only |

## 6.6 Cost control

Model calls are metered per agent — tokens, latency, cost — and dashboarded, with budget alarms
per organisation. A3 (top-tier model) is the cost driver; its per-feed cost is expected to be cents
against hours of modeller time, but retry loops are capped at three to prevent pathological spend.
`[OPEN]` — the cost model is unvalidated (Q9).

---

# Chapter 7 — Catalogs and access control

> **Status:** `[WORKING]`. One structural question is `[OPEN]` and blocking: whether identity may
> be shared across organisations (Q3).
> **Feedback wanted:** governance and risk review of §7.3 and §7.6. The information barrier is
> enforced here or nowhere.

Single metastore in the primary operating region. Workspaces may be shared or per-organisation —
**isolation comes from catalog grants, not workspace boundaries.**

## 7.1 Catalog matrix

| Catalog | Purpose | Notes |
|---|---|---|
| `<org>_bronze` | Raw only, as landed — no typing, cleaning or deduplication | One schema per source system |
| `<org>_silver` | Canonical core plus conformed long tail | §7.2 |
| `<org>_gold` | Use-case projections | One schema per use case or consumer group |
| `<org>_dev`, `<org>_test` | Sandbox and CI | Wiped on schedule |
| `ref_master` | Cross-organisation hubs, key maps and reference data | **The only cross-organisation data surface** |
| `edw_meta` | State, audit, quality events, profiling results | Platform-owned |

## 7.2 Silver schema layout

```
<org>_silver
├── instrument/                     # subject-area schema (Tier 1)
│     h_instrument                  # hub (shared hubs live in ref_master)
│     l_instrument_issuer           # link
│     s_instrument__bloomberg       # satellite, one per source
│     s_instrument__refinitiv
│     v_instrument_current          # generated current view — what Gold reads
├── position/ …
└── conformed/                      # Tier 3 long tail
      <source_system>__<table>      # cleaned, typed, deduplicated, source-shaped
```

Naming: `h_` hub, `l_` link, `s_<entity>__<source>` satellite, `v_<entity>_current` current view,
`km_<entity>` key map. Versioned satellites append `_v2` for major changes only.

## 7.3 Principals

**Groups** (synchronised from the corporate directory): stewards, modellers, engineers and
analysts per organisation, plus a central platform group and a design authority group.

**Service principals — the security core:**

| Principal | Used by | Permissions |
|---|---|---|
| `sp_<org>_ingest` | Ingestion jobs | Write to that organisation's Bronze only |
| `sp_<org>_runtime` | Production pipelines | Read Bronze; write Silver; shared-catalog writes only via a governed pipeline; no Gold |
| `sp_<org>_gold` | Gold refresh | Read Silver and reference data; write Gold |
| `sp_<org>_agent` | Build-time agents | Read metadata; sampled, masked, row-limited reads of Bronze; **write to the sandbox only**; git access via pull request only |
| `sp_sentinel` | A7 | Read operational metadata; **no data access at all** |
| `sp_meta` | Controller and sync jobs | Read/write operational catalog; catalog comment and tag writes |

**Hard rules.** No service principal spans organisation data boundaries, except shared-catalog
writes which go through a single governed pipeline. No human has write access to production
catalogs — production changes only through pull request and CI. **Agent principals have zero
production write access anywhere.**

## 7.4 Grants are code

Grants live in a per-organisation directory in the pipelines repository and are applied by CI —
reviewable, versioned, revertible. A5 proposes Gold grants only through this path; no agent
executes a grant directly.

## 7.5 Sensitive data

Classification from the contract becomes a catalog tag, from which column masks and row filters are
generated by the same pipeline. The profiling engine reads under an elevated, audited identity but
**emits only aggregates** — the model never receives raw restricted values, and sampling respects
masks. A disagreement between the identifier scan and the human classification blocks contract
compilation and routes to the steward and data governance.

## 7.6 Cross-organisation sharing — `[OPEN]`

Everything cross-organisation goes through the shared catalog (identity and reference data) or an
explicit Gold-to-Gold share with a signed-off use-case specification naming both organisations.
Default is deny.

The barrier is auditable as a single question: *list all grants on one organisation's catalogs to
principals outside that organisation.* A scheduled query answers it, and should return only
documented exceptions.

**The open question (Q3):** this design places instrument and party hubs in the shared catalog, so
that both organisations resolve to the same identity. If the barrier rules forbid shared
*identity* — not merely shared data — hubs must be duplicated per organisation with a
reconciliation process, which is a materially different and worse design. **This is a governance
decision and it blocks the entity model.**

---

# Chapter 8 — Silver physical standards and code generation

> **Status:** the **model** is `[SETTLED]` (ADR-3). The **implementation mechanism** is `[OPEN]`
> and under active review — see §8.6, which may replace hand-written merge logic with a native
> platform feature.
> **Feedback wanted:** §8.6 is the most consequential open item in this document. Anyone with
> Lakeflow experience, please weigh in.

These standards are what make code generation possible: **every table type has exactly one shape
and one loading pattern**, so the generator is filling a template rather than programming.

## 8.1 Hub — identity, and nothing else

```sql
CREATE TABLE h_instrument (
  instrument_hk   STRING NOT NULL,  -- hash of the business key
  business_key    STRING NOT NULL,  -- enterprise identifier, or composite
  first_seen_at   TIMESTAMP,
  first_seen_src  STRING
) -- insert-only; NEVER altered
```

## 8.2 Key map — the generalised security master

```sql
CREATE TABLE km_instrument (
  instrument_hk  STRING NOT NULL,
  source_system  STRING NOT NULL,   -- 'bloomberg'
  source_key     STRING NOT NULL,   -- vendor identifier
  valid_from     TIMESTAMP, valid_to TIMESTAMP
)
```

Resolves many source identifiers to one enterprise identity. This is the pattern most firms
already run for instruments; here it is applied to every entity.

## 8.3 Descriptive satellite — history by construction

```sql
CREATE TABLE s_instrument__bloomberg (
  instrument_hk   STRING NOT NULL,
  load_ts         TIMESTAMP NOT NULL,
  effective_from  TIMESTAMP NOT NULL,
  effective_to    TIMESTAMP,        -- NULL means current
  is_current      BOOLEAN,
  hash_diff       STRING NOT NULL,  -- hash over the payload columns
  record_source   STRING,
  name STRING, asset_class STRING, currency STRING  -- payload from the mapping
)
```

Grain: **one current row per hub key.** All timestamps UTC. `effective_from` is the source event
time where the contract declares one, otherwise load time.

## 8.4 Multi-active satellite — time series and periodic data — `[SETTLED]`

*This distinction was discovered by building the prototype, not by review, and it is easy to get
wrong.*

A descriptive satellite is correct for attributes that *describe* an entity — name, currency,
sector. It is **wrong** for data that is inherently a series: daily prices, quarterly valuations,
periodic ratings. Loading a multi-date batch into a descriptive satellite silently keeps only the
most recent row and discards the rest.

For those, the period becomes part of the grain:

```sql
CREATE TABLE s_instrument_price__bloomberg (
  instrument_hk  STRING NOT NULL,
  price_date     DATE   NOT NULL,   -- part of the grain
  effective_from TIMESTAMP, effective_to TIMESTAMP, is_current BOOLEAN,
  hash_diff      STRING, record_source STRING,
  close_px       DECIMAL(18,6)
) -- grain: (instrument_hk, price_date); history applies WITHIN each period
```

**Why this matters commercially:** when a vendor restates one period's value — a corrected
valuation, an adjusted price — only that period gets a new version. Every other period, every
other source, and the hub are untouched, and the original reported figure remains queryable. That
is the audit trail a restatement requires, and a descriptive satellite cannot provide it.

**Rule for modellers and A3:** an attribute belongs in a multi-active satellite if the source can
legitimately supply more than one value for the same entity at the same time, distinguished by a
period or category key. Choosing wrong is a modelling error the Validator catches through a grain
reconciliation check.

## 8.5 Links, current views, conformed tables

- **Link** — hub-key pairs plus load time; insert-only.
- **Current view** (`v_<entity>_current`) — generated view joining the hub to the current slice of
  the preferred satellites, using a documented per-attribute source precedence taken from the
  entity specification. **Gold reads these**, not raw satellites.
- **Conformed Silver** (Tier 3) — typed, renamed to consistent casing, deduplicated on the declared
  grain, with a quarantine table for quality failures. Source-shaped otherwise. Bronze is never
  conformed: it stays raw so it can serve as the replay log (§8.8).

## 8.6 `[OPEN]` — hand-written merge, or the platform's native change-data-capture?

**Raised late; potentially removes a meaningful amount of generated code.**

The design above specifies a hand-written merge pattern: stage, resolve identity, compute a hash,
then close-and-insert on change. Databricks Lakeflow provides `AUTO CDC INTO … STORED AS SCD TYPE 2`
(formerly `APPLY CHANGES INTO`), which computes Slowly Changing Dimension Type 1 and Type 2
natively, from either a change feed or successive snapshots [[2]](#r2).

It covers, as platform features, three things this design hand-built:

| Hand-built here | Native equivalent [[2]](#r2) |
|---|---|
| Merge with hash comparison, close-on-change, insert-new | `AUTO CDC INTO … STORED AS SCD TYPE 2` |
| Tie-break when a restatement carries the same effective date as the row it corrects — *a real bug that had to be found and fixed* | `SEQUENCE BY STRUCT(timestamp_col, id_col)` — ties broken by the second field |
| Hash column list controlling which changes create a version | `TRACK HISTORY ON * EXCEPT (…)` |

`AUTO CDC FROM SNAPSHOT` is separately relevant: many enterprise feeds arrive as complete snapshots
with no change feed, and it derives the changes by comparing successive snapshots.

**If adopted:** less generated code, fewer places to introduce subtle history bugs, and
platform-maintained semantics. It *strengthens* ADR-2 rather than weakening it — the mapping
specification remains the input; only the rendering target changes.

**To verify before deciding:** whether a composite `KEYS` clause cleanly expresses the multi-active
grain; the requirement for serverless or Pro/Advanced pipeline editions; the fixed
`__START_AT`/`__END_AT` column naming versus this design's `effective_from`/`effective_to`; and
behaviour under backfill and replay.

**Owner and timing:** platform lead, before any further template work in Phase 0.

## 8.7 Template inventory

| Template | Renders | Instantiated per |
|---|---|---|
| `bronze_ingest.py.j2` | Ingestion | Source feed |
| `hub_keymap_upsert.sql.j2` | Hub and key-map upsert | Entity × source |
| `satellite_merge.sql.j2` | Satellite load | Entity × source |
| `link_load.sql.j2` | Link insert | Relationship × source |
| `conformed.sql.j2` | Tier-3 conformed table | Table |
| `current_view.sql.j2` | Precedence-merged current view | Entity |
| `gold_view.sql.j2` | Use-case projection | View |
| `expectations.j2` | Data-quality expectations | Table |
| `test_pipeline.py.j2` | Unit tests and fixtures | Pipeline |

Rendering is deterministic and templates are versioned, so **a template fix can be re-rendered
across every existing mapping**, producing one reviewable mass pull request. That is how thousands
of pipelines get upgraded uniformly, and it is the practical payoff of ADR-2.

## 8.8 Schema evolution — what happens to what

| Source change | Automated action | Reload? |
|---|---|---|
| Column added | Minor bump; satellite evolves additively | No |
| Type widened | Minor bump; column evolves | No |
| Column dropped | Major; column retained but stops populating | No |
| Column renamed | Major; drop-plus-add unless the steward confirms a rename | No |
| Type narrowed or semantics changed | Major; new satellite version, old frozen and queryable | New satellite only |
| Grain or key changed | Major, human-led (runbook R6) | New satellite lineage only |
| Vendor replaced | New satellite and key-map entries; old satellite frozen | No |

**Invariant: no change class touches hubs, links, other satellites, or Gold view contracts.**
A Gold view referencing a deprecated column fails at regeneration time in CI — caught at build, not
by a user at query time.

## 8.9 Backfill and reload policy

The **unit of reload is one satellite**. A rebuild re-runs that satellite's mapping over Bronze
history — which is why Bronze must remain a complete, immutable replay log (`[OPEN]`, Q6: retention
policy must support this). Backfills run the same generated code with a date parameter, write to a
shadow table, are validated by reconciliation checks, and are then swapped atomically.

---

# Chapter 9 — Team and graduated autonomy

> **Status:** `[WORKING]` — and this is the least evidenced chapter in the document. The autonomy
> model is a designed hypothesis with a measurement plan; no agreement statistics exist yet.
> **Feedback wanted:** the promotion criteria in §9.4. Are they strict enough for risk acceptance,
> and loose enough to ever actually be met?

**The objective is not headcount reduction.** It is eliminating human-typed code and minimising
human-typed text. Humans direct, edit, approve and audit; agents draft and type. The headcount
taper in §9.3 is an outcome, not the goal — the same people redirect from typing to judgment.

## 9.1 Organisation

```
                    EDW Design Authority (governance body)
                    entity model · major changes · precedence · autonomy sign-off
                                       │
   ┌───────────────────────────────────┼──────────────────────────────────┐
   │                                   │                                  │
 Platform Pod (central)         Modelling (central)          Organisation-aligned
 · platform engineers           · modellers                  · data stewards (part-time)
 · ops engineers (shared        · A8 Reviewer works          · design-authority representative
   on-call rotation)              under this function        · engineer liaison (Phases 1–2)
 · owns: agent factory,         · owns: entity specs,
   templates, controller,         mapping approvals,
   CI, operational catalog        tiering appeals
                                       │
                    Data Governance / Risk (existing enterprise function)
                    classification disputes · barrier audit · autonomy risk acceptance
```

## 9.2 Roles

| Role | Owns | Notably does *not* |
|---|---|---|
| **Platform engineer** | Agent factory, templates, schemas, controller, CI, golden sets, model version pins | Type most of the code — Claude Code drafts, the engineer reviews every pull request |
| **Ops engineer** | Exceptions queue, novel incidents, backfill swaps, on-call | Write pipeline code |
| **Modeller** | Entity specifications (editing drafts), escalated mapping reviews, monthly audit sample | Write code at all; author specs from blank pages |
| **Data steward** | Intake confirmation, conflict resolution, classification, priority | Anything technical — this role is business knowledge |
| **Design authority** | Entity proposals, major changes, precedence rules, autonomy levels (with Risk) | Day-to-day approvals |

The steward is **the only role that must exist inside each organisation from day one.**

## 9.3 Headcount by phase

| Role | Phase 1 (pilot) | Phases 2–3 (scale-out) | Steady state |
|---|---|---|---|
| Platform engineers | 2 | 3 | 2–3 |
| Ops engineers | covered by platform | 2–3 | ~2 |
| Modellers | 1 | 2 | ~1 |
| Engineer liaison per organisation | 1 | 1 per org | 0 (absorbed) |
| Stewards | 1 | part-time per org | part-time per org |
| **Total (excluding stewards)** | **~4–5** | **~8–11** | **~6–8** |

Scale-out is deliberately the peak: humans verify everything while the statistics that justify
automation are accumulated. Autonomy promotions then shrink the steady state.

## 9.4 Graduated autonomy — `[WORKING]`

### Levels

- **L0 — human decides.** The agent proposes; a named human approves every instance.
- **L1 — human on exception.** Automatic approval when *all* policy conditions hold; humans see
  disagreements, exceptions, and a **10% random audit sample** reviewed within five business days.
- **L2 — human on audit.** As L1, with the sample reduced to 2–5% and quarterly policy review.

### What may and may not be automated

| Decision | Proposer | Checker | Target | Never automated because |
|---|---|---|---|---|
| Intake confirmation | A1 | Steward | **L0 permanently** | Business meaning is human ground truth |
| Tier-3 mapping | A3 | A8 | L2 | — |
| Tier-1 mapping | A3 | A8 | L1 | Custom SQL, shared entities and tier promotions stay L0 |
| Merge, low-risk | A4 | A6 + policy | L2 | — |
| Merge, high-risk | A4 | A6 | **L0 permanently** | High blast radius |
| Quality triage, backfill to shadow | A9 | Playbook gates | L1–L2 | Atomic swap keeps an approval click |
| Entity specification change | A10 draft | Design authority | **L0 permanently** | Systemic blast radius — this is the stable core |
| Grants and access | A5 proposes | Data owner + platform | **L0 permanently** | Information barrier |
| Incident command (novel) | — | — | **Human** | Accountability and operational-resilience obligations |

### Promotion and demotion

**Promotion L0→L1** requires: at least 200 consecutive decisions where the human verdict agreed
with the would-be automated verdict at ≥95%; zero major changes misclassified; a golden set
covering the decision type; and a policy document signed by the design authority and Risk.
**L1→L2** requires three clean months.

**Demotion is automatic** on any of: a material error found in the audit sample; any production
incident root-caused to an automated decision; a model or skill version change (drops one level
until requalification); or agreement drift below 90%.

### Accountability

Every automated decision writes an audit record: decision type, autonomy level, policy version,
proposer and checker skill and model versions, input hash, audit-sample flag, and auditing human.
**"Who approved this?" always has an answer** — either a named person, or "policy version X at L1,
signed off by the design authority and Risk on <date>, audit-sampled by <person>".

## 9.5 Who types what

| Artifact | Drafted by | Human role |
|---|---|---|
| Pipeline code, tests, expectations, Gold views, grants | Renderer | **None** — CI rejects hand-edits |
| Mappings | A3 | Approve or edit |
| Entity and use-case specifications | A10 | Edit and merge (permanent) |
| Intake forms | A1 pre-fill | Correct via structured form; write business meaning (permanent) |
| Skills and prompts | A10 | Review and merge |
| Platform code | Claude Code, engineer-directed | Review every pull request (permanent) |
| Custom transform SQL | A3, occasionally human | Line-by-line review (permanent) |

## 9.6 North-star metrics

- **Human-authored lines merged per month, per repository** — target approximately zero for specs
  and pipelines (enforced); small but non-zero for the agent factory.
- **Edit distance on agent drafts** — trending to zero flags an autonomy promotion candidate;
  staying high flags a skill that needs work.
- **Blank-page violations** — artifacts created without an agent draft.
- **Unresolved `TODO(human)` age** — drafts waiting on human ground truth.

---

# Chapter 10 — Implementation plan

> **Status:** `[WORKING]` — sequence is firm, durations are estimates.
> **Feedback wanted:** Phase 0's exit criterion deliberately excludes all AI. Is that the right
> discipline, or over-cautious?

## Phase 0 — Foundation (weeks 1–6)

Catalog matrix and grants; three repositories scaffolded; schemas for all six specification types;
agent runner framework and tool library with scoping enforced; operational catalog and controller
skeleton; CI/CD skeleton; governed model endpoint approved.

**Exit criterion:** a *hand-written* mapping renders through templates, deploys to the sandbox and
passes validation end to end. **No AI is involved — prove the deterministic spine first.** Also
resolve §8.6.

## Phase 1 — Pilot, one domain (weeks 7–14)

Public markets, instrument and valuation entities, three to five real feeds — deliberately
including two overlapping price vendors so the hub/satellite benefit is demonstrated rather than
asserted.

Entity specifications drafted by A10 and edited by modellers. Agents A1–A6 brought online one at a
time, in order, with **100% human verification** of every output during this phase; the first
golden sets are built from those reviews. One real Gold use case shipped to a friendly consumer
team.

**Exit criteria:** a new feed onboarded end to end in under five working days with no more than
three human touch points; and a simulated vendor schema change absorbed with zero reload of
untouched tables.

## Phase 2 — Industrialise (weeks 15–26)

Sentinel, drift detection and catalog sync live; dashboards and nightly digests; golden-set CI and
the monthly correction harvest running. **A8 Reviewer runs in shadow mode**, reviewing every
mapping alongside the human so agreement statistics accumulate. Scale to roughly 50 feeds across
two organisations — onboarding a second organisation is what proves the isolation model.

**Exit criteria:** Tier-3 feeds onboard with about one human touch point; mapping approval queue
under a week; agent pull-request acceptance above 80% without edits.

## Phase 3 — Scale-out (months 7–12)

Bulk registration driven by Gold use-case demand. Hundreds of feeds live, long tail flowing as
conformed Silver. A template upgrade exercised as a mass regeneration at least once, to prove
fleet-wide maintainability. **First autonomy promotions** once criteria are met.

## Top risks

| Risk | Severity | Mitigation |
|---|---|---|
| Entity model designed wrong early | **Highest** — it is the thing everything else depends on | Pilot on the best-understood domain; design authority; major-gated changes |
| Agent mapping quality poor, so review burden exceeds savings | High | Confidence scores route attention; golden-set CI; 100% verification in Phase 1 before any trust is extended |
| Steward bottleneck at intake | High | Pre-filled forms; ten-minute target; nightly digest; five-day escalation |
| History corruption from subtle merge bugs | High | Mandatory integrity checks in validation; reconciliation counts every run; possibly eliminated by §8.6 |
| Model or vendor change alters agent behaviour | Medium | Pinned versions per skill; golden replay before any upgrade; automatic autonomy demotion |
| Cost creep | Medium | Per-agent metering, budgets, retry caps |

## Success metrics, dashboarded from day one

Onboarding lead time by tier · human touch points per feed · agent pull-request acceptance rate ·
percentage of source changes absorbed with zero reload (target 100% by construction) · quality
expectation pass rate · steward and modeller queue depth · cost per onboarded feed · human-authored
lines merged and edit distance on drafts.

---

# Chapter 11 — Operations

> **Status:** `[WORKING]` — runbooks are written but unexercised outside the prototype.
> **Feedback wanted:** R6 (grain or key change) is the most dangerous procedure here. Does it look
> safe enough to whoever will actually run it?

## 11.1 Runbooks

| ID | Situation | Ownership |
|---|---|---|
| **R1** | Onboard a new source feed | Steward initiates; three human gates |
| **R2** | Source schema drift detected | Minor: automatic. Major: engineer follows the change-class table. **Never hand-edit generated code** — fix the mapping or template and regenerate |
| **R3** | Quality expectation failures spike | A9 playbook; distinguish a data problem from a rule problem before acting |
| **R4** | Rebuild or backfill one satellite | A9 to shadow table, reconciliation, then a human-approved atomic swap; old table retained 30 days |
| **R5** | Promote a Tier-3 table into the canonical model | Modeller confirms the target entity; the feed re-enters the flow |
| **R6** | **Grain or business-key change** — the most dangerous change | Human-led. Treated as a new source generation, run in parallel with the old for at least one cycle, cross-reconciled, then precedence flipped. Design-authority sign-off recorded |
| **R7** | Agent misbehaviour or a bad merged artifact | Revert; root-cause in the skill or template; add the case to goldens; regenerate |
| **R8** | Model or skill upgrade | Golden replay, then shadow canary on ten live feeds, then promote the version pin |
| **R9** | Access request or barrier audit | Grants-as-code pull request only; scheduled cross-organisation grant audit; quarterly recertification |
| **R10** | Source decommission | Contract retired, satellites frozen as-of date, precedence updated, Bronze retained |

## 11.2 Monitoring and service levels

| Signal | Threshold |
|---|---|
| Pipeline freshness against contracted service level | Alert on breach |
| Expectation pass rate | Warn below 99%, page below 95% |
| Onboarding queue age | Human-awaiting over five business days → weekly review |
| Agent job failures | Three consecutive → platform engineer |
| Model spend per organisation | Budget alarm |
| Drift backlog | Over 20 open per organisation → prioritisation session |
| Cross-organisation grant audit | **Any unexpected row → immediate** |

**Dashboards:** onboarding funnel by state; quality heatmap by organisation × source; agent quality
(acceptance rate, edit distance, golden regressions); cost. **Nightly digest per role** so no
individual has to go looking for their queue.

## 11.3 Cadence

| Frequency | Activity |
|---|---|
| Daily | Sentinel digest triage by the on-call engineer |
| Weekly | Operations review — queue ages, quality trends, cost |
| Fortnightly | Design authority — entity proposals, major changes, precedence, autonomy |
| Monthly | Golden harvest; audit-sample and agreement-rate review; grant recertification sampling |
| Quarterly | Full access recertification; autonomy policy review; **disaster drill — restore a satellite from Bronze replay** |

---

# Chapter 12 — Prototype and evidence

> **Status:** `[SETTLED]` for what it covers — but read §12.3 carefully, because what it does *not*
> cover matters as much.
> **Feedback wanted:** what else should the prototype prove before Phase 0 starts?

A runnable miniature exists in `prototype/`, sized for Databricks Free Edition: two organisations
with isolated catalogs, shared reference data both can read, five simulated source feeds, the full
Bronze → Silver → Gold flow, and a second data batch that exercises change absorption.

## 12.1 What it demonstrates

| Design claim | How it is shown |
|---|---|
| Organisational isolation by catalog grants | One analyst sees only their organisation's Gold; the other organisation's catalogs are invisible, not merely unqueryable |
| Shared reference data readable by both | Both Gold views join the same shared asset-class table |
| Shared identity without shared data | The instrument hub lives in the shared catalog but is not granted to analysts |
| Stability under source change | Batch 2 renames an instrument and adds a new one: **one satellite changes; nothing is reloaded** |
| History by construction | Renamed instrument shows a closed old version and a current new one |
| Restatement handling | A corrected valuation versions **only that period**; the original figure remains queryable |
| Graceful divergence between sources | An instrument present in one vendor's feed but not the other's lands cleanly in one satellite |

## 12.2 Verified by execution

The loading patterns were tested with asserted checks before delivery:

- History semantics: idempotent reload, close-on-change, new-key insert, value-reverts-to-previous,
  exactly one current row per grain.
- Multi-active satellites: time series preserved across a multi-date batch; restatement versions
  only the affected period.
- Restatement tie-break when a correction shares the effective date of the row it corrects.
- Full two-batch Bronze → Silver → Gold flow with a rename, a new entity, a new period and a
  restatement.

**Two real defects were found this way**, both invisible to document review: a SQL construct that
parses on Databricks but not on open-source Spark, and — more substantively — the missing
multi-active satellite pattern, which would have silently discarded price history.

## 12.3 Explicitly not verified

- **Databricks-specific execution.** Delta merge, Unity Catalog data-definition statements, grant
  behaviour and pipeline expectations could not run in the test environment. These are the parts to
  watch on first execution.
- **Agent quality — nothing at all.** No agent has been built. Every quality, throughput and
  autonomy claim in Chapters 5 and 9 is a hypothesis.
- **Economics.** Cost per onboarded feed is unmeasured.

## 12.4 Deliberate simplifications

Notebooks rather than declarative pipelines (Free Edition allows one active pipeline); user grants
rather than groups and service principals (no account console); a simplified business key; no link
tables. None of these affect the claims in §12.1.

---

# Chapter 13 — Decision register

> **Status:** the consolidated record. Every decision, its status, and who can overturn it.
> **Feedback wanted:** this table is the intended landing point for disagreement. Cite the
> identifier.

## 13.1 Architecture decisions

| ADR | Decision | Status | Reversal cost | Overturned by |
|---|---|---|---|---|
| ADR-1 | Agents at build time only | `[SETTLED]` | Low — could add runtime agents later | Architecture + Risk |
| ADR-2 | Models emit specifications; templates emit code | `[SETTLED]` | **Very high** — restructures the agent factory | Architecture |
| ADR-3 | Silver is hub/link/satellite over business entities | `[SETTLED]` | **Very high** — restructures the warehouse | Architecture + modelling |
| ADR-4 | Demand-pull tiering | `[SETTLED]` | Low — a scheduling choice | Design authority |
| ADR-5 | Catalog per organisation × layer; shared masters | `[WORKING]` | High if reversed after build | **Governance/Risk (Q3)** |
| ADR-6 | Own controller, not an external orchestrator | `[WORKING]` | Medium — rises after Phase 1 | Architecture (Q4) |
| ADR-7 | Graduated autonomy with proposer/critic separation | `[WORKING]` | Low — can simply stay at L0 | Design authority + Risk |
| ADR-8 | Draft-by-agent, edit-by-human | `[SETTLED]` | Low | Architecture |

## 13.2 Design decisions

| # | Question | Decision | Status |
|---|---|---|---|
| D1 | Where do agents run? | Build time only | `[SETTLED]` |
| D2 | What do models produce? | Specifications, not code | `[SETTLED]` |
| D3 | Free prose or structured specs? | YAML plus prose body | `[SETTLED]` |
| D4 | One large agent or many narrow? | Many narrow, structured inputs and outputs | `[SETTLED]` |
| D5 | What shapes Silver? | The business domain, via Data Vault | `[SETTLED]` |
| D6 | Model the whole estate upfront? | No — demand-pull | `[SETTLED]` |
| D7 | Who owns which contract fields? | Human owns undiscoverable; agent owns observable; **compiler blocks on conflict** | `[SETTLED]` |
| D8 | Does conformed data live in Bronze? | **No — Bronze is raw only** | `[SETTLED]` |
| D9 | How do specifications version? | Semantic versioning drives regeneration scope | `[WORKING]` |
| D10 | Orchestration mechanism | State table plus jobs | `[WORKING]` |
| D11 | Shared identity across organisations | Shared hubs in a common catalog | `[WORKING]` |
| D12 | Can mapping approval be automated? | Yes, via critic plus graduated autonomy | `[WORKING]` |
| D13 | Can operations be automated? | Runbooks become gated playbooks | `[WORKING]` |
| D14 | Is the goal headcount reduction? | **No — eliminating human-typed code** | `[SETTLED]` |
| D15 | Who writes platform code? | Claude Code drafts; engineers direct and review | `[WORKING]` |
| D16 | Do specifications start blank? | No — always agent-drafted | `[WORKING]` |
| D17 | One satellite kind or two? | Two — descriptive and multi-active | `[SETTLED]` |
| D18 | Repository visibility | De-identified; history rewritten | `[SETTLED]` |
| D19 | Hand-written merge or native change-data-capture? | **Under review** | `[OPEN]` |

## 13.3 Corrections that improved the design

Recorded because someone will eventually propose the rejected option again.

1. **Bronze must stay raw** (D8). The original draft had a "conformed Bronze" tier, which violated
   medallion discipline and would have compromised Bronze's role as replay log. Databricks' own
   guidance is explicit that Bronze limits cleanup and preserves raw fidelity [[1]](#r1).
2. **The goal is less human coding, not fewer humans** (D14). This reframed the autonomy work from
   "how few people can run this" to "where does human-typed text still enter the system" — a better
   question that produced better metrics.
3. **A prototype finds what review does not** (D17). The multi-active satellite gap was invisible in
   the design documents and obvious within minutes of running data through code.
4. **Read the platform documentation before hand-building platform features** (D19). Native
   change-data-capture covers a meaningful part of what was hand-rolled, including the exact
   tie-break bug that had to be debugged.

---

# Chapter 14 — Open questions and feedback register

> Ordered by how much rework the answer could cause. **Each needs an owner and a date.**

| # | Question | Blocks | Needs a decision from | Status |
|---|---|---|---|---|
| **Q1** | Native `AUTO CDC` instead of hand-written merge? (§8.6) | Template work, Phase 0 | Platform lead | `[OPEN]` |
| **Q2** | What is the canonical Tier-1 entity list? | **Everything** | Modellers + design authority | `[OPEN]` |
| **Q3** | May identity be shared across organisations? (§7.6) | Entity model, catalog design | **Governance / Risk** | `[OPEN]` |
| **Q4** | Is an enterprise orchestrator mandated? (ADR-6) | Controller build | Architecture | `[OPEN]` |
| **Q5** | Approved route to model access? | Phase 0 completion | Model governance | `[OPEN]` |
| **Q6** | Does Bronze retention support indefinite replay? | Recovery design (§8.9) | Data governance + infrastructure | `[OPEN]` |
| **Q7** | Do steward, modeller and engineer roles exist with capacity? | Phase 1 start | Organisation leadership | `[OPEN]` |
| **Q8** | How is Party/Issuer handled across organisations? | Entity model | Modellers + Risk | `[OPEN]` |
| **Q9** | What is the cost model? | Budget approval | Platform lead + finance | `[OPEN]` |
| **Q10** | How does this coexist with the existing estate? | Migration planning | Architecture | `[OPEN]` |
| **Q11** | Non-tabular sources (documents, unstructured)? | Nothing yet | — | `[PARKED]` |
| **Q12** | Streaming or intraday requirements? | Nothing yet | Consumer teams | `[PARKED]` |
| **Q13** | Semantic layer over Gold? | Nothing yet | — | `[PARKED]` |

### The two that matter most

**Q2 — the entity list.** Everything in this design is built on the canonical entity model, and the
entity names currently in these documents were drafted from general finance knowledge, not from the
business. This must be replaced with real domain input before Phase 1. It is also the hardest thing
to change later: entity specifications are the deliberately stable core.

**Q3 — cross-organisation identity.** This is not an engineering question. If the information
barrier permits a shared instrument and party identity spine, the design works as written. If it
does not, hubs must be duplicated per organisation with reconciliation — worse, but survivable if
known now rather than discovered in Phase 2.

---

# Appendix A — Glossary

| Term | Meaning |
|---|---|
| **Agent** | A language model given a narrow task, structured inputs and outputs, and a restricted set of tools |
| **AUTO CDC** | Databricks API computing Slowly Changing Dimension Type 1/2 automatically from a change feed or snapshots; replaces `APPLY CHANGES` [[2]](#r2) |
| **Blast radius** | The set of objects affected by a change — the smaller and more predictable, the better |
| **Bronze / Silver / Gold** | The three medallion layers: raw, validated-and-modelled, business-ready [[1]](#r1) |
| **CDC (Change Data Capture)** | Capturing inserts, updates and deletes from a source for downstream replay |
| **Conformed** | Cleaned, typed, renamed and deduplicated, but still shaped like the source |
| **Data Vault 2.0** | Modelling method built on hubs, links and satellites, for many volatile sources [[5]](#r5) |
| **Delta Lake** | The transactional table format underlying Databricks tables |
| **Grain** | What one row of a table represents (for example, one row per instrument per trading day) |
| **Golden set** | Stored input/output pairs used to regression-test a prompt when it changes |
| **Hub** | Data Vault table holding only an entity's business key — the stable identity anchor |
| **Idempotent** | Running it twice produces the same result as running it once |
| **Jinja** | Python templating engine used to render code from specification files |
| **Key map** | Table resolving each source system's identifier to the enterprise identifier |
| **Lakeflow Declarative Pipelines** | Databricks' declarative pipeline framework (formerly Delta Live Tables) |
| **Link** | Data Vault table representing a relationship between hubs |
| **Medallion architecture** | Databricks' recommended multi-layer data design pattern [[1]](#r1) |
| **Multi-active satellite** | Satellite whose grain includes a period or category key, so it can hold several concurrent values per entity (for example, a price series) |
| **Provenance** | A tag on each specification field recording whether a human, a measurement or an agent produced it |
| **Satellite** | Data Vault table holding one source's descriptive attributes for an entity, with effective dating |
| **SCD Type 2 (Slowly Changing Dimension Type 2)** | History technique: on change, close the current row with an end date and insert a new one [[6]](#r6) |
| **Semantic versioning** | Version scheme where major/minor/patch signals the severity of a change |
| **Service principal** | Non-human identity used by automated jobs, with its own permissions |
| **Unity Catalog** | Databricks' governance layer for catalogs, schemas, tables, permissions and lineage |

---

# Appendix B — References

<a id="r1"></a>**[1]** Databricks — *What is the medallion lakehouse architecture?*
<https://docs.databricks.com/aws/en/lakehouse/medallion>
Layer definitions. Directly supports D8: Bronze should "limit data cleanup or validation", preserve
raw fidelity, and enable "reprocessing and auditing by retaining all historical data"; Silver is
where deduplication, normalisation and type casting belong; Gold is where dimensional modelling and
aggregation belong.

<a id="r2"></a>**[2]** Databricks — *The AUTO CDC APIs: Simplify change data capture with pipelines*
<https://docs.databricks.com/aws/en/ldp/cdc>
Native Slowly Changing Dimension Type 1 and Type 2, multi-column sequencing via `STRUCT`,
`TRACK HISTORY ON * EXCEPT`, and `AUTO CDC FROM SNAPSHOT` for sources without a change feed.
Central to §8.6 / Q1.

<a id="r3"></a>**[3]** Databricks — *Data Vault Best Practice & Implementation on the Lakehouse*
<https://www.databricks.com/blog/data-vault-best-practice-implementation-lakehouse>
Vendor guidance: insert-only raw vault, source metadata retained in the table, raw versus business
vault separation.

<a id="r4"></a>**[4]** Databricks — *Data warehousing modeling techniques and their implementation
on the Databricks Lakehouse Platform*
<https://www.databricks.com/blog/2022/06/24/data-warehousing-modeling-techniques-and-their-implementation-on-the-databricks-lakehouse-platform.html>
Compares dimensional modelling, Data Vault and normalised approaches on the platform.

<a id="r5"></a>**[5]** Linstedt, D. & Olschimke, M. — *Building a Scalable Data Warehouse with
Data Vault 2.0*, Morgan Kaufmann, 2015.

<a id="r6"></a>**[6]** Kimball, R. & Ross, M. — *The Data Warehouse Toolkit*, 3rd edition,
Wiley, 2013.

<a id="r7"></a>**[7]** Cockburn, A. — *Hexagonal Architecture (Ports and Adapters)*, 2005.

<a id="r8"></a>**[8]** Databricks — *Use Unity Catalog with pipelines*
<https://docs.databricks.com/aws/en/ldp/unity-catalog> · *Pipeline limitations*
<https://docs.databricks.com/aws/en/ldp/limitations> · *Free Edition limitations*
<https://docs.databricks.com/aws/en/getting-started/free-edition-limitations>

---

# Appendix C — Artifact index

| Artifact | Location | Purpose |
|---|---|---|
| Design journal | `docs/00-design-journal.md` | The living record of reasoning and open questions |
| Working documents | `docs/01`–`docs/09` | Maintained detail behind each chapter |
| Specification templates | `templates/` | The six specification types plus a code template |
| Prototype | `prototype/` | Runnable miniature; see `prototype/INSTALL.md` |
| Executive summary | `docs/EXECUTIVE-SUMMARY.md` | Two-page version for senior management |

---

*End of document. Comments to the decision register (Chapter 13) or the open-questions register
(Chapter 14), citing the identifier.*
