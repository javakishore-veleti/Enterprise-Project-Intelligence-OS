# Product Overview

**Enterprise Project Intelligence OS** — an evidence-grounded, multi-agent *risk analyst* for software delivery.

## The core problem

Delivery risk is knowable from issue-tracker data long before it hurts — but nobody can see it in time. The signals (a reopened bug, a blocker piling up, one person owning everything, a stalling backlog) are spread across millions of issues and changelogs that no human reads. So risk gets discovered late — in a slipped release or a post-mortem — instead of early.

Existing tools don't close the gap:
- **BI dashboards** show raw counts (open issues, velocity) but don't *interpret* them into "this is a risk, here's why, here's what to do."
- **Manual risk reviews** are subjective, inconsistent, infrequent, and rarely evidence-backed.
- **Nothing** gives a *combined* portfolio view of risk across many projects.

> Teams are data-rich but risk-blind — the evidence exists, the interpretation doesn't.

**Who feels it:** delivery leads, PMOs, engineering directors, portfolio owners — anyone accountable for whether things ship on time and at quality.

## What it does

```
Issue-tracker data (Jira)  →  deterministic evidence metrics (no LLM)
    →  ~16 specialist LLM agents (LangGraph) interpret the evidence
    →  ranked, evidence-grounded delivery RISKS + mitigations + reports
    →  surfaced through the Project-Tracker & Admin portals
```

## Core features

| # | Feature | What it does |
|---|---|---|
| 1 | **Evidence ingestion** | Batch-loads large issue-tracker datasets into a normalized evidence store — resumable, checkpointed, governed |
| 2 | **Deterministic metrics** (no LLM) | Objective facts: backlog growth, reopen rate, blockers, issue aging, velocity + trend, contributor concentration, critical-defect ratio, dependency depth |
| 3 | **Multi-agent risk analysis** | ~16 LangGraph specialists (schedule, quality, dependency, resource, backlog, forecasting…) interpret evidence into ranked, explained findings |
| 4 | **Review pipeline** | Validates, de-dupes, correlates, scores, runs a critic loop, then generates executive / mitigation / project reports |
| 5 | **Portfolio risk** | Group projects and evaluate their combined risk |
| 6 | **Governed UIs** | Project-Tracker (live risk intelligence) + Admin (config/ops) with dynamic dashboards |
| 7 | **Governance & trust** | Evidence-grounding invariant, audit trail, tracing, framework-agnostic agent seam |

## Value add / differentiators

1. **Evidence-grounded, not hallucinated.** Hard invariant: raw records *never* reach the LLM. Deterministic code computes the facts first; agents only interpret those. Every finding cites the real number. This is the moat vs. "ask a chatbot about my Jira."
2. **Interpretation, not just charts.** Turns "32% reopen rate, 608 blockers, velocity 30 vs 67" into *"HIGH schedule risk because rework churn is consuming closure capacity"* + a mitigation plan.
3. **Consistent & objective at scale.** The same deterministic scoring across every project; reads millions of issues no human could; agents explain, humans decide.
4. **Portfolio-level.** Combined risk across a group of projects — the view executives never get.
5. **Proactive & explainable.** Scheduled runs + a live dashboard catch risk early; per-agent breakdowns, reports, audit, and traces make it defensible.

## What it is *not* (honest scope)

- **Jira is the only evidence source today** (via the public JiraRepos dataset). The architecture is source-agnostic in principle, but currently Jira-shaped — a GitHub Issues / Azure DevOps connector would be net-new.
- It is an **intelligence/analytics** product, not workflow automation — it tells you the risk; it does not reassign tickets or edit the tracker.
- Value depends on **data quality** — sparse or non-standard trackers yield weaker signal.

## Secondary (architectural) focus

It also serves as a reference implementation of *governed* multi-agent orchestration: the evidence-grounding invariant, LangGraph coordination with a framework-agnostic adapter seam, and strictly-layered microservices behind a single governed boundary. See `CLAUDE.md` for the engineering detail.
