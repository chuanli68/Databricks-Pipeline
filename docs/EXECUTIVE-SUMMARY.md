# Enterprise Data Warehouse — Executive Summary

**For:** senior management · **Date:** 2026-08-10 · **Status:** proposal for review
**Full design:** `docs/DESIGN.md` (14 chapters) · **Decision needed:** see §7

---

## 1. The problem in one paragraph

We need an enterprise data warehouse covering tens of thousands of source tables across public
markets, private markets and private equity — with strict information barriers between them. We do
not have, and cannot hire, enough data modellers and engineers to build it the conventional way.
Worse, conventional warehouses are only stable because engineers absorb constant change by hand:
every time a data vendor alters a feed, someone rewrites a load and rebuilds history. At our scale
that model does not work at any headcount we would be willing to fund.

## 2. The proposal

**Use AI agents to build the warehouse, not to run it.**

Agents read written specifications of each data source, propose how it maps into our business
model, and generate the pipeline code — submitting it for human approval like any engineer would.
Once approved, what runs in production is ordinary, reviewed, deterministic code. **No AI sits in
the data path.** Every number in the warehouse can be explained without reference to a model's
judgment.

Underneath, the warehouse is deliberately structured so that a change in any single source can only
affect a small, predictable set of tables — never trigger a broad rebuild. This is achieved with an
established industry method (Data Vault 2.0) that Databricks explicitly supports, chosen because
its main drawback — it is repetitive and tedious to build by hand — is exactly what makes it
well-suited to machine generation.

## 3. Why we believe it works

| Claim | Basis |
|---|---|
| A source change never forces a warehouse rebuild | Structural property of the chosen model; **demonstrated in a working prototype** — a vendor rename, a new instrument and a corrected valuation were all absorbed with nothing reloaded |
| Generated code is reviewable at scale | Reviewers check a 30-line specification, not 300 lines of code; all pipelines share one reviewed template |
| Information barriers hold | Enforced by platform permissions, not by agent behaviour. An agent working for one organisation physically cannot read another's data. Demonstrated in the prototype |
| Regulated-industry defensibility | Every automated decision is logged with its policy, versions and inputs. "Who approved this?" always has an answer |

A working prototype exists today. It is small, but it is real code with real tests, and building it
found two design defects that document review had missed — including one that would have silently
discarded price history.

## 4. What it costs

| | Pilot (months 1–4) | Scale-out (months 4–12) | Steady state |
|---|---|---|---|
| **Team (FTE)** | ~4–5 | ~8–11 | **~6–8** |
| **Composition** | Platform engineers, one modeller, one steward | Adds operations engineers and a second organisation | Small central pod plus part-time business stewards |

Scale-out is deliberately the most expensive period: humans verify every agent output while we
accumulate the evidence needed to safely automate approvals. Costs then fall as that evidence
accrues.

**Important framing:** the objective is *not* headcount reduction. It is removing hand-written code
from the critical path so that the specialists we do have spend their time on judgment — what the
data means, how the business model should be structured — rather than on typing pipelines. The
headcount figures are a consequence of that, not the goal.

Cloud and AI running costs are not yet modelled (open question Q9). The dominant AI cost is the
mapping agent, expected to be cents per source against hours of modeller time — but this needs
validating, not asserting.

## 5. What is proven, and what is not

We think it is important to be precise about this rather than present a uniformly confident case.

**Proven:** the data model's stability properties, tested with executable checks — history
correctness, restatement handling, and absorption of source changes without reloads. Organisational
isolation via platform permissions.

**Not proven:**

- **Agent quality — nothing at all.** Not one agent has been built. Every claim about how accurate
  the mappings will be, and therefore how much human review is really saved, is a hypothesis with a
  measurement plan attached. Phase 1 exists to test it, with 100% human verification throughout.
- **Economics.** Cost per onboarded source is unmeasured.
- **The business entity model.** The entity names in the design were drafted from general finance
  knowledge, not from our business. This must be replaced with real input from our modellers before
  the pilot.

**The single biggest risk** is designing the core business entity model wrong early, because
everything else is built on it. Mitigation: pilot on the best-understood domain, and gate changes
to it through a design authority.

## 6. Approach to control and governance

- Agents propose; humans approve. Approval can be progressively automated **only** on measured
  evidence — at least 200 decisions at 95%+ agreement with human reviewers, with random audit
  sampling and automatic reversion if quality drifts.
- Four things are never automated, by design: confirming what data means, changes to the business
  model, granting data access, and command of novel incidents.
- Access decisions remain human, reviewed as code, and independently auditable — a scheduled query
  answers "has any barrier been crossed?" at any time.
- AI model access is intended to run through a governed, logged platform endpoint with no data
  leaving the approved boundary — subject to model-governance approval (open question Q5).

## 7. What we need from leadership

Three of these are not engineering decisions and are blocking.

| # | Decision required | From | Impact if delayed |
|---|---|---|---|
| **1** | **May the three organisations share a common identity spine** (one instrument, one counterparty definition) while keeping their data separate? | Governance and Risk | Blocks the business model design. If not permitted, the design is materially worse but workable — we need to know now, not in month 6 |
| **2** | **Approve the governed AI model endpoint** | Model governance | Blocks the end of Phase 0 |
| **3** | **Confirm business stewards exist in each organisation** with a few hours a month to confirm what their data means | Organisation leadership | This is the one role that cannot be automated. Without it the whole approach stalls |
| 4 | Confirm whether a corporate orchestration platform is mandated | Architecture | Cheap to accommodate now, expensive later |
| 5 | Confirm raw data can be retained indefinitely as the replay log | Data governance | Determines our recovery model |

## 8. Recommendation

Proceed to **Phase 0 (six weeks)**, which deliberately involves **no AI at all**. It builds and
proves the deterministic foundation — catalogs, permissions, templates, deployment — using a
hand-written example. If that foundation does not work, we learn it cheaply and nothing has been
staked on the agent hypothesis.

Then **Phase 1 (eight weeks)**: a pilot on one domain with three to five real data feeds, every
agent output verified by a human, exiting on two concrete tests — a new feed onboarded in under
five working days, and a simulated vendor change absorbed with nothing rebuilt.

That gives a genuine go/no-go point at roughly month four, with real evidence rather than
projections, for an outlay of four to five people.

---

## Appendix — Glossary for this summary

| Term | Meaning |
|---|---|
| **Data Vault 2.0** | An established data-modelling method designed for absorbing many changing sources; separates stable identity from volatile attributes |
| **Medallion architecture** | Databricks' recommended three-layer structure: raw → validated → business-ready |
| **Steward** | A business person who confirms what a dataset means — not a technical role |
| **Blast radius** | How far the effects of one change spread; the design goal is to keep it small and predictable |
| **Phase 0 / Phase 1** | Foundation without AI; then a supervised pilot with AI |
