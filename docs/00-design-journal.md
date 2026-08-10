# 00 — Design Journal (living document)

**Status:** working draft, actively edited · **Last updated:** 2026-08-10

---

## How to read this document

This is the *reasoning* behind the design. Documents 01–09 are the specification — what the
system is. This one is why it is that way: the arguments, the alternatives rejected, the
corrections made along the way, and everything still unresolved.

**Written for a mixed audience.** Sections 1–3 assume no data-warehousing background and
explain the industry terms as they arise. Sections 4 onward get more technical. The
[glossary](#glossary) defines every term and acronym; the [references](#references) point to the
standards and vendor documentation this design builds on, so nothing here has to be taken on
trust.

**Conventions for editing.** Section 4 is the decision log — add a row when a question closes,
never delete one, mark superseded entries instead. Section 5 is the open-questions register, and
is the working queue. Status tags used throughout:

| Tag | Meaning |
|---|---|
| `[SETTLED]` | Decided; unlikely to reopen without new information |
| `[WORKING]` | Current answer, still soft |
| `[OPEN]` | Unresolved, needs an answer |
| `[PARKED]` | Deliberately deferred |
| `[SUPERSEDED]` | Replaced by a later decision |

---

## 1. The problem

Build an enterprise data warehouse on Databricks using the **medallion architecture** — the
three-layer pattern Databricks recommends, in which data moves through Bronze (raw), Silver
(validated and modelled) and Gold (business-ready) layers, improving in quality at each step
[[1]](#r1).

Four constraints apply, and together they rule out the conventional approach:

1. **Scale of inputs.** Tens of thousands of source tables from many systems and vendors, whose
   schemas change without notice.
2. **Organisational segregation.** Data is separated by organisation — public markets, private
   markets, private equity — with information barriers between them that are a control
   requirement, not a preference.
3. **No staff.** Not enough data modellers or engineers to hand-build this, now or later.
   Hiring to the size of the problem is not an option.
4. **Stability is the hard requirement.** A change to an input source must not trigger a rebuild
   or reload of everything downstream. A vendor adding a column must not cost a weekend.

Constraint 4 shapes everything else. Most warehouses are stable *in practice* because a team of
engineers quietly absorbs the churn. Remove the team (constraint 3) and stability has to come
from the architecture instead.

**The starting idea** was: give every Bronze input a clear written description, define how the
data should be used and what the target schema is, and let AI agents transform it forward. That
instinct was right. Most of the work since has been making it precise enough to actually execute.

---

## 2. Background: the two industry patterns this builds on

Readers who know Data Vault and dimensional modelling can skip to §3.

### 2.1 Dimensional modelling (Kimball)

The classical warehouse pattern [[6]](#r6): facts (measurements) surrounded by dimensions
(descriptive context), optimised for querying. Its answer to "an attribute changed and I need
history" is the **Slowly Changing Dimension (SCD)**, of which **Type 2** is the common form:
instead of overwriting a changed value, you close the existing row (stamp it with an end date)
and insert a new one, so the table holds the full history of what was true when.

Dimensional modelling is excellent for consumption and poor for absorbing source churn — a
restructured source generally means a restructured dimension.

### 2.2 Data Vault 2.0 (Linstedt)

A modelling method designed for exactly the problem of many volatile sources feeding one
warehouse [[5]](#r5). It splits the model into three table types:

- **Hub** — the business key of an entity, and nothing else. One row per real-world thing.
- **Link** — a relationship between hubs.
- **Satellite** — descriptive attributes attached to a hub or link, *one satellite per source*,
  with effective-dating built in.

The design intent is a **stable core (hubs) with flexible edges (satellites)**, resilient to
environmental change — which is precisely constraint 4. Databricks publishes prescriptive
guidance for implementing Data Vault on the lakehouse [[3]](#r3) and positions it alongside
dimensional modelling as a supported approach [[4]](#r4).

Data Vault's well-known drawback is that it is verbose and repetitive to build, and joins-heavy
to query. Both objections matter less here, for reasons in §3.4 and §3.5.

### 2.3 Where this design sits

**Silver is Data Vault; Gold is dimensional.** The stable, source-absorbing layer uses hubs,
links and satellites. The consumption layer projects that into the friendly shapes analysts
expect. This is the combination Databricks' own modelling guidance describes as a normal
lakehouse pattern [[4]](#r4), and it matches the medallion layer definitions: Silver is where
cleansing, deduplication and normalisation happen; Gold is where dimensional modelling and
aggregation happen [[1]](#r1).

---

## 3. Current synthesis — the six load-bearing ideas

If any one of these is wrong, revisit everything downstream of it.

### 3.1 Agents run at build time, never at runtime

AI agents read specifications, generate mappings and code, and open pull requests for humans to
review. The production pipelines that actually move data are ordinary, reviewed, deterministic
code with no language model in the data path.

*Why:* determinism, auditability, cost, and the ability to answer "why does this number look
like that" without saying "the model decided". A consequence worth stating plainly: an agent
failure is a failed pull request, never corrupted data.

### 3.2 Language models emit specifications; templates emit code

The model's output is structured YAML — a source contract, a mapping. Deterministic **Jinja**
templates (a standard Python templating engine; think mail-merge for code) render that YAML into
pipeline code.

*Why this is the load-bearing idea:*

- Review becomes tractable at scale — a reviewer checks a 30-line mapping, not 300 lines of SQL.
- Generated code is uniform across thousands of pipelines, because they share one template.
- A template fix becomes a fleet-wide upgrade by regenerating everything from unchanged mappings.
- It removes the failure mode where a model invents a novel code shape that works but which
  nobody recognises six months later.

*The cost:* anything a template cannot express needs a `custom_transform` escape hatch
containing hand-reviewed SQL. Keep that surface small and watch whether it grows. If it does,
the template library is what needs fixing, not the review process.

### 3.3 Silver is modelled on the business domain — not on sources, not on use cases

Sources churn; use cases multiply. Neither can define the shape of the stable layer. What has
not changed in decades is what a Position, an Instrument, or a Fund actually *is*.

The software-architecture analogy that makes this click is **hexagonal architecture** (also
called ports-and-adapters) [[7]](#r7): the domain model sits at the centre, every external system
is an adapter around it, and adapters never dictate the domain's shape. Silver is the domain
layer; every source system is an adapter.

### 3.4 Identity is separated from attributes

Following Data Vault: hubs hold identity, satellites hold attributes, and a key map resolves each
source system's identifier to the enterprise one (the security-master pattern, generalised).

The passport analogy: the hub is the passport number — permanent identity. Satellites are the
stamps each country adds. New country, new stamps; nobody reissues the passport.

Three properties follow, and they are the answer to constraint 4:

- **History comes for free.** A satellite *is* a Slowly Changing Dimension Type 2 table by
  construction. There is no per-table history design decision to get wrong.
- **Bounded blast radius.** Any source change touches one mapping and one satellite. A vendor
  swap means a new satellite while the old one is frozen but still queryable. There is no change
  class in the design that triggers a warehouse-wide reload.
- **Ideal for code generation.** Satellite loading is brutally repetitive — the same merge,
  hash-comparison and effective-dating logic, thousands of times, differing only in column lists.
  That tedium is the standard human objection to Data Vault, and precisely why a machine should
  write it.

The accepted trade-off: Silver becomes join-heavy and unfriendly to query directly. That is
fine — nobody queries Silver. Gold exists to project it into friendly shapes, and Gold is cheap,
regenerable views.

### 3.5 Demand-pull tiering

Modelling 30,000 tables upfront is impossible with the available staff and mostly worthless, since
most will never be queried.

- **Tier 1** — core entities (roughly 50–200) get full canonical modelling.
- **Tier 2** — reference data, lightly conformed.
- **Tier 3** — the long tail lands as *conformed Silver*: typed, renamed, deduplicated, but still
  source-shaped. It is promoted into the canonical model only when a Gold use case needs it.

### 3.6 Humans edit; agents draft and type

The goal is **not fewer people**. It is zero human-typed pipeline code and minimal human-typed
text. Every artifact starts as an agent draft; humans contribute judgment as edits and approvals.
Human approval gates are converted into policies with measured agreement statistics — not simply
removed.

Permanently human by design: business meaning (grain, definitions, quirks — ground truth an agent
would otherwise plausibly fabricate), entity model changes, access grants, and incident command
for novel failures.

---

## 4. Decision log

| # | Question | Decision | Status | Why / note |
|---|---|---|---|---|
| D1 | Where do agents run? | Build time only | `[SETTLED]` | Determinism, audit, cost. ADR-1 |
| D2 | What do language models produce? | Specifications (YAML), not code | `[SETTLED]` | Review tractability, uniformity, mass regeneration. ADR-2 |
| D3 | Free prose or structured specs? | YAML frontmatter + prose body | `[SETTLED]` | Agents drift on free text; YAML can be validated in continuous integration |
| D4 | One large agent or many narrow ones? | Narrow agents with structured inputs/outputs | `[SETTLED]` | Same reason you don't hand a junior engineer the whole warehouse as one ticket |
| D5 | What shapes Silver? | Business domain, via Data Vault 2.0 hub/link/satellite [[5]](#r5) | `[SETTLED]` | Constraint 4. ADR-3 |
| D6 | Model the whole estate upfront? | No — demand-pull tiering | `[SETTLED]` | ADR-4 |
| D7 | Who owns which contract fields? | Human owns the undiscoverable; agent owns the observable; the compiler merges and **blocks on conflict** | `[SETTLED]` | Never let an agent silently pick a winner on grain or data sensitivity |
| D8 | Does conformed data live in Bronze? | **No — Bronze is raw only; conformed data is Silver** | `[SETTLED]` | *Chuan's correction.* Confirmed by Databricks guidance: Bronze should "limit data cleanup or validation" and preserve raw fidelity for reprocessing and audit [[1]](#r1) |
| D9 | How do specifications version? | Semantic versioning, like an API; patch/minor/major drives what regenerates | `[WORKING]` | Table in doc 02 §4 |
| D10 | Orchestration | Delta state table + Databricks Jobs controller | `[WORKING]` | ADR-6. Revisit if an enterprise orchestrator is mandated — see Q3 |
| D11 | Shared identity across organisations? | Shared hubs and key maps in a `ref_master` catalog | `[WORKING]` | ADR-5. A governance decision, not a technical one — see Q2 |
| D12 | Can mapping approval be automated? | Yes — via an independent reviewer agent plus graduated autonomy (L0→L1→L2) | `[WORKING]` | Proposer/critic separation; promotion only on measured agreement. ADR-7 |
| D13 | Can operational work be automated? | Runbooks become agent-executed playbooks with hard verification gates | `[WORKING]` | Novel incidents stay human |
| D14 | Is the goal headcount reduction? | **No — the goal is eliminating human-typed code** | `[SETTLED]` | *Chuan's correction.* Reframed the metrics to human-authored lines merged and edit distance on drafts. ADR-8 |
| D15 | Who writes the platform code? | Claude Code drafts; platform engineers direct and review | `[WORKING]` | The platform is the fixed point of the recursion — someone must author the constraints |
| D16 | Do specifications start from a blank page? | No — agents draft entity and use-case specs; profiling pre-fills intake forms | `[WORKING]` | A steward editing a pre-filled form takes ten minutes; a blank template sits in a queue for weeks |
| D17 | One satellite kind or two? | Two: *descriptive* (grain = hub key) and *multi-active* (grain = hub key + period) | `[SETTLED]` | **Found by building the prototype.** A descriptive satellite silently collapses a multi-date price batch to its latest row. Restatement handling depends on getting this right |
| D18 | Repository visibility and naming | De-identified; git history rewritten | `[SETTLED]` | Public repository. See §8 |
| D19 | Hand-rolled `MERGE` or the platform's native change-data-capture? | **Under review — likely switch to `AUTO CDC`** | `[OPEN]` | See Q1; this is the most consequential open item |

---

## 5. Open questions

Ordered by how much rework the answer could cause.

### Q1 — Should satellite loading use `AUTO CDC` instead of hand-rolled `MERGE`? `[OPEN]`

**This surfaced late and may simplify the design considerably.** Databricks Lakeflow pipelines
provide `AUTO CDC INTO ... STORED AS SCD TYPE 2` (formerly `APPLY CHANGES INTO`), which computes
Slowly Changing Dimension Type 1 and Type 2 natively from either a change feed or from successive
snapshots [[2]](#r2). Notably it covers, as platform features, three things this design hand-built:

| Hand-built here | Native equivalent |
|---|---|
| `MERGE` with hash-difference comparison, close-on-change, insert-new | `AUTO CDC INTO ... STORED AS SCD TYPE 2` |
| Restatement tie-break by arrival timestamp *(a bug I had to find and fix)* | `SEQUENCE BY STRUCT(timestamp_col, id_col)` — multi-column sequencing, ties broken by the second field |
| Hash column list controlling which changes create a version | `TRACK HISTORY ON * EXCEPT (...)` |

`AUTO CDC FROM SNAPSHOT` is separately relevant: many enterprise feeds arrive as full snapshots
with no change feed, and it derives the changes by comparing successive snapshots [[2]](#r2).

**Implications if adopted:** less generated code, fewer places to introduce subtle history bugs,
and platform-maintained semantics. The code-generation templates would emit `AUTO CDC` statements
rather than merge logic — which strengthens rather than weakens D2, since the mapping
specification stays the input either way.

**What to check before deciding:** whether composite `KEYS` cleanly expresses the multi-active
satellite grain (hub key + period); the requirement for serverless or Pro/Advanced pipeline
editions [[2]](#r2); the fixed `__START_AT` / `__END_AT` column naming versus the design's
`effective_from` / `effective_to`; and behaviour on backfill and replay.

### Q2 — What is the canonical Tier-1 entity list? `[OPEN]`

The highest-stakes unknown after Q1. Candidates: Instrument, Party/Issuer, Portfolio, Position,
Transaction, Valuation; Fund, Deal, Portfolio Company for private markets. But the *actual* list,
definitions, and edge cases need a workshop with the modellers — the names currently in the
documents were invented from general finance knowledge, not from the business. Getting the entity
model wrong early is the single worst failure mode, because everything else is built on it.

### Q3 — Can identity legitimately be shared across organisations? `[OPEN]`

The design places instrument and party hubs in a shared `ref_master` catalog, readable by every
organisation's runtime. If the information-barrier rules forbid even shared *identity* — not just
shared data — hubs must be duplicated per organisation with a reconciliation process, which is a
materially different and worse design. A question for Risk and Governance, not engineering.
Blocks doc 05 §6.

### Q4 — Is an enterprise orchestrator mandated? `[OPEN]`

The controller design (a state table plus Databricks Jobs) assumes freedom to stay inside
Databricks. If Airflow or Azure Data Factory is the corporate standard, the state machine
survives but the controller is replaced. Cheap to change now; expensive later.

### Q5 — What is the approved route to model access? `[OPEN]`

Assumed: Claude via Databricks Mosaic AI external models — a governed, logged endpoint with no
data egress. Needs model-governance sign-off before Phase 0 completes.

### Q6 — Does Bronze retention support replay indefinitely? `[OPEN]`

The whole recovery story — "the unit of reload is one satellite, replayed from Bronze" — assumes
Bronze retains raw history indefinitely. Databricks describes exactly this role for Bronze:
preserving fidelity and "enabling reprocessing and auditing by retaining all historical data"
[[1]](#r1). But if the firm's retention policy bounds it, satellite rebuilds beyond the window
become impossible and recovery needs rethinking.

### Q7 — Do the three human roles exist, with capacity? `[OPEN]`

Stewards, modellers, engineers — per organisation. The design assumes a steward exists in each
organisation who can confirm intake forms within days. If not, the intake gate becomes the
bottleneck and nothing else matters.

### Q8 — How is Party/Issuer handled across organisations? `[OPEN]`

Instrument identity is the easy case. A counterparty or general partner appearing in both public
and private markets is harder: same legal entity, different systems, different sensitivity.
Related to Q3 but messier.

### Q9 — What is the cost model? `[OPEN]`

Per-agent metering is designed but unbudgeted. The entity-mapping agent (top-tier model) is the
cost driver. Needs a sanity check against modeller hours saved before anyone asks the question.

### Q10 — How does this coexist with the existing estate? `[OPEN]`

Designed greenfield. In reality there is an existing warehouse, existing catalog and lineage
tooling, and existing consumers. Migration and coexistence are not designed at all.

### Q11 — What about non-tabular sources? `[PARKED]`

The design assumes tabular inputs from databases and feeds. Documents, PDFs, unstructured
research and semi-structured payloads are out of scope for now. Worth revisiting — agents are
unusually good at this, and it may be where the differentiated value lies.

### Q12 — Streaming or intraday requirements? `[PARKED]`

Everything is batch. Streaming tables are used as a mechanism, but the design has no answer for
genuine real-time needs. Establish whether any use case actually requires it before building for
it.

### Q13 — A semantic layer over Gold? `[PARKED]`

The catalog-sync job already pushes descriptions into Unity Catalog comments, which
natural-language query tools consume. There may be a natural extension where Gold plus rich
metadata yields a usable natural-language layer. Not designed; noted as opportunity.

---

## 6. Proven versus assumed

The distinction between "the design works" and "the design has not yet failed".

**Verified by execution** (local simulation with asserted tests):

- Slowly Changing Dimension Type 2 semantics: idempotent reload, close-on-change, new-key insert,
  value-reverts-to-a-previous-value, exactly one current row per grain.
- Multi-active satellite: time series preserved across a multi-date batch; a restatement versions
  only the affected period.
- Restatement tie-break: when a correction carries the same effective date as the row it corrects,
  arrival timestamp resolves the order. *This was a real bug, found by tracing expected row counts.*
- Full two-batch Bronze → Silver → Gold flow, including a rename, a new entity, a new period, and
  a restatement.

**Not verified — watch these on the first real run:**

- Delta Lake `MERGE`, Unity Catalog data-definition statements, `GRANT` behaviour, and pipeline
  expectations. None could execute in the test environment (the sandbox had no access to the
  required Delta libraries).
- Anything about agent *quality*. Not one agent has been built. Every claim about mapping
  accuracy, review burden and autonomy promotion is a hypothesis with a measurement plan attached
  — no more than that.
- The economics. Cost per onboarded feed is unmeasured.

**Assumed without evidence:** everything in §5.

---

## 7. Things that changed my mind

The corrections worth remembering, because someone will propose the rejected option again.

1. **Bronze must stay raw** (D8). The original draft had a "conformed Bronze" tier, which quietly
   violated medallion discipline and would have compromised Bronze's role as the replay log.
   Databricks' own guidance is explicit that Bronze limits cleanup and preserves raw fidelity
   [[1]](#r1).
2. **The goal is less human coding, not fewer humans** (D14). This reframed the entire autonomy
   discussion — from "how few people can run this" to "where does human-typed text still enter the
   system", which is a better question and produced better metrics.
3. **A prototype finds what review does not** (D17). The multi-active satellite gap and the
   restatement tie-break were both invisible in the design documents and obvious within minutes of
   running data through real code. Build early, build small.
4. **Read the platform documentation before hand-building platform features** (D19/Q1). The
   native change-data-capture API covers a meaningful part of what was hand-rolled here, including
   the exact tie-break problem that had to be debugged. A cheaper lesson learned late than never.

---

## 8. Housekeeping

- The repository is public and de-identified; git history was rewritten to remove organisational
  references from all prior commits. A pre-rewrite backup bundle is retained separately.
- Assume pre-rewrite content may already have been cloned by bots or mirrors — the rewrite reduces
  exposure but does not undo it.
- Sample data (instrument universe, timezone examples) is deliberately generic.

---

## 9. Next actions

1. **Resolve Q1** — evaluate `AUTO CDC` against the hand-rolled merge before writing any more
   code-generation templates. Highest leverage item on this list.
2. Run the prototype end-to-end on Databricks Free Edition and confirm the unverified list in §6.
3. Take Q2 to the modellers — produce the real Tier-1 entity list.
4. Take Q3 and Q5 to Governance and Risk. Both are blocking and neither is an engineering decision.
5. Build the deterministic spine (Phase 0) before any agent — prove that templates → bundle →
   deploy → validate works with a hand-written mapping.
6. Only then build the first agent.

---

## Glossary

| Term | Meaning |
|---|---|
| **Agent** | A language model given a narrow task, structured inputs and outputs, and a restricted set of tools |
| **AUTO CDC** | Databricks API that computes Slowly Changing Dimension Type 1/2 automatically from a change feed or snapshots; replaces `APPLY CHANGES` [[2]](#r2) |
| **Bronze / Silver / Gold** | The three medallion layers: raw, validated-and-modelled, business-ready [[1]](#r1) |
| **CDC (Change Data Capture)** | Capturing inserts, updates and deletes from a source so they can be replayed downstream |
| **Conformed** | Cleaned, typed, renamed and deduplicated, but still shaped like the source |
| **Data Vault 2.0** | Modelling method built on hubs, links and satellites, designed for many volatile sources [[5]](#r5) |
| **Delta Lake** | The transactional table format underlying Databricks tables |
| **Grain** | What one row of a table represents (e.g. "one row per instrument per trading day") |
| **Hub** | Data Vault table holding only an entity's business key — the stable identity anchor |
| **Idempotent** | Running it twice produces the same result as running it once |
| **Jinja** | Python templating engine used to render code from specification files |
| **Key map** | Table resolving each source system's identifier to the enterprise identifier |
| **Lakeflow Declarative Pipelines** | Databricks' declarative pipeline framework (formerly Delta Live Tables) |
| **Link** | Data Vault table representing a relationship between hubs |
| **Medallion architecture** | Databricks' recommended multi-layer data design pattern [[1]](#r1) |
| **Multi-active satellite** | Satellite whose grain includes a period or category key, so it can hold several concurrent values per entity (e.g. a price series) |
| **Satellite** | Data Vault table holding one source's descriptive attributes for an entity, with effective dating |
| **SCD Type 2 (Slowly Changing Dimension Type 2)** | History-keeping technique: on change, close the current row with an end date and insert a new one, preserving what was true when [[6]](#r6) |
| **Semantic versioning** | Version scheme where major/minor/patch signal the severity of a change |
| **Service principal** | Non-human identity used by automated jobs, granted its own permissions |
| **Unity Catalog** | Databricks' governance layer for catalogs, schemas, tables, permissions and lineage |

---

## References

<a id="r1"></a>**[1]** Databricks — *What is the medallion lakehouse architecture?*
<https://docs.databricks.com/aws/en/lakehouse/medallion>
Defines the Bronze/Silver/Gold layers. Directly supports D8: Bronze should "limit data cleanup or
validation", preserve raw fidelity, and enable "reprocessing and auditing by retaining all
historical data"; Silver is where deduplication, normalisation and type casting belong.

<a id="r2"></a>**[2]** Databricks — *The AUTO CDC APIs: Simplify change data capture with pipelines*
<https://docs.databricks.com/aws/en/ldp/cdc>
Native Slowly Changing Dimension Type 1 and Type 2 support, multi-column sequencing via `STRUCT`,
`TRACK HISTORY ON * EXCEPT`, and `AUTO CDC FROM SNAPSHOT` for sources without a change feed.
Central to Q1.

<a id="r3"></a>**[3]** Databricks — *Data Vault Best Practice & Implementation on the Lakehouse*
<https://www.databricks.com/blog/data-vault-best-practice-implementation-lakehouse>
Vendor guidance for Data Vault on Databricks: insert-only raw vault, source metadata retained in
the table, raw vault versus business vault separation.

<a id="r4"></a>**[4]** Databricks — *Data warehousing modeling techniques and their implementation on the Databricks Lakehouse Platform*
<https://www.databricks.com/blog/2022/06/24/data-warehousing-modeling-techniques-and-their-implementation-on-the-databricks-lakehouse-platform.html>
Compares dimensional modelling, Data Vault and normalised approaches on the platform.

<a id="r5"></a>**[5]** Linstedt, D. & Olschimke, M. — *Building a Scalable Data Warehouse with
Data Vault 2.0*, Morgan Kaufmann, 2015. The definitive treatment of hubs, links and satellites.

<a id="r6"></a>**[6]** Kimball, R. & Ross, M. — *The Data Warehouse Toolkit*, 3rd edition, Wiley,
2013. Dimensional modelling and the Slowly Changing Dimension types.

<a id="r7"></a>**[7]** Cockburn, A. — *Hexagonal Architecture (Ports and Adapters)*, 2005. The
domain-at-the-centre pattern that §3.3 borrows.

<a id="r8"></a>**[8]** Databricks — *Use Unity Catalog with pipelines*
<https://docs.databricks.com/aws/en/ldp/unity-catalog> · *Pipeline limitations*
<https://docs.databricks.com/aws/en/ldp/limitations> · *Free Edition limitations*
<https://docs.databricks.com/aws/en/getting-started/free-edition-limitations>
Governance integration and the platform constraints the prototype had to work within.

---

## Changelog

| Date | Change |
|---|---|
| 2026-08-10 | Added references, glossary and background section; spelled out acronyms; recorded D19/Q1 (`AUTO CDC` versus hand-rolled merge) after reading the platform documentation |
| 2026-08-10 | Initial draft assembled from design sessions to date |
