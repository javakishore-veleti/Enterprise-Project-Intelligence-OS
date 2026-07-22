# Agentic Verbs — Investigate · Predict · Decide

The product's reason to exist is **Agentic AI augmentation** of issue-tracker data — not listing it (Jira / GitHub / Azure DevOps already list). See `ENTERPRISE-SCALE-ARCHITECTURE.md` and the memory law "agentic-first is the product."

**The pattern for every verb:** the agent *did the work* → here is its **conclusion + evidence + confidence** → the human **steers or approves**. The human is a reviewer/decider, never an operator. If a screen could exist in Jira, it is not the hero.

---

## 🔍 Investigate — "Deploy an investigator, watch it think"

Not a project register. You point an autonomous **Investigation Agent** at a risk/project (or type *"why is Sakai slipping?"*) and it investigates end-to-end:

1. **Plans** — forms hypotheses to test (reopen churn? blocker pile-up? bus-factor? stalled dependency?).
2. **Works, visibly** — a live reasoning trace, each step citing evidence it pulled from the evidence store: *"214 reopened issues → 68% in Auth → 1 owner holds 60% → over-allocated across 3 projects."*
3. **Concludes** — a **causal chain** + root cause + confidence + the exact issues cited + the single next action.
4. **Steerable** — *"what about the vendor API?"* → it re-investigates.
5. **Proactive** — surfaces investigations nobody asked for (*"3 findings across 2 projects share one root cause"*).

**Agents:** NEW **Investigation Agent** — a LangGraph tool-using (ReAct) loop over evidence-store tools (query issues / histories / links / contributors / metrics), verified by a critic pass; reuses `risk_correlation` for the cross-project case.

**Endpoint (contract):** `POST /api/v1/analysis/investigate` `{ project_key, question? }` →
`{ project_key, question, hypotheses[], steps[{action, observation, hypothesis}], root_cause, causal_chain[], confidence, evidence[{kind, detail, count}], recommended_action, run_id, generated_at }`.

---

## 🔮 Predict — "Agents that forecast and simulate, and show their reasoning"

Not a trend chart. Forecasting + **scenario** agents that make a *call* and defend it:

- **Delivery/release forecast** — *"Sakai release: 63% on-time, likely 2-week slip"* **with the why** (velocity −55%, blocker burn rate, dependency risk) + confidence + evidence.
- **Scenario simulator (Digital Twin)** — *"move 2 engineers to Payments?"* / *"delay Feature A 2 weeks?"* → reasons over dependencies + velocity: *"Payments recovers 8d, Checkout slips 5d, net portfolio risk −12pts."* Impossible in Jira.
- **Early-warning** — proactively: *"Sprint 12 completion probability dropped 91% → 63% — here's why,"* before it's obvious.

**Agents:** `delivery_forecasting` (have) + NEW scenario-simulation agent.

---

## ✅ Decide — "Agents draft the plan; you approve and it acts"

Not a "pick agents and run" form. A **planning + decision-support** agent:

- **Drafted action plan** — prioritized actions, *suggested owners* (from contributor data), sequencing, estimated recovery, trade-offs — grounded in evidence.
- **Options with predicted outcomes** — *"A: reallocate (recover 3d, risk to Payments); B: descope Feature X (recover 5d, customer impact)"* + confidence.
- **Steerable** — *"what if we can't get the vendor?"* → re-plans.
- **Acts, with approval** — creates the Jira tickets / assignments for the chosen plan. Agent → decision → action.

**Agents:** `mitigation_planning` (have) + NEW decision-support/options agent + an action-execution step.

---

## Coverage vs. the 15 classic PM strategies

That canonical "15 project management strategies" list is a spec for our agents — inverted from *"a tool helps a human do X"* to *"an agent does X and briefs the human."* ~9 of 15 are already covered by the 16-agent roster (risk management, resource allocation, quality, reporting, cross-team correlation, live briefing…). Net-new agents implied: **goal-clarity, change-impact, time-box/overrun, knowledge-graph, retrospective** — none need new data, only new agents over the evidence we already have.

## Build order
1. **Investigation Agent** (Investigate) — the flagship; its tool-loop + evidence-streaming becomes the pattern the others inherit.
2. Scenario-simulation agent (Predict).
3. Decision-support/options + action-execution (Decide).
