# UI Design Thinking

The design north-star for the Enterprise Project Intelligence OS portals. The product is an **AI-powered operational intelligence platform** over issue-tracker data (Jira today; GitHub / Azure DevOps / ServiceNow / Slack / CI-CD / observability tomorrow). It should feel like an **AI executive assistant / intelligent advisor** — not another ticket manager or enterprise dashboard.

## The guiding principle

**Every page answers four questions immediately — visible in 5 seconds, no clicking, no searching:**

1. **What is happening?**
2. **Why is it happening?**
3. **What will happen next?**
4. **What should I do now?**

When every view follows this pattern, the app feels like an intelligent advisor.

## First impression (within 5 seconds)

Professional software immediately answers: *What is happening? What needs my attention? What is the AI telling me? What should I do next?* Everything important is immediately visible.

## Navigation — minimal (professionals hate 50-option menus)

Left nav, ~12 items max:

`Home · Projects · Issues · AI Insights · Risks · Dependencies · Teams · Analytics · Knowledge · Automations · Reports · Administration`

Nothing more.

## The Homepage = an AI Executive Assistant

Not dozens of charts. Instead:

**Greeting + hero stats**
> Good Morning Kishore — 17 projects monitored · 438 issues analyzed · 7 critical risks detected · 12 teams healthy · **AI Confidence 94%**

**Today's Attention** (the single most important thing)
> **Project Mercury** — Critical deployment blocker · Probability of schedule slip **89%**
> Recommended actions: Review database migration · Escalate vendor API · Move Story 2483 · **Estimated recovery: 3 days**

**AI Executive Summary** (last 24h — the most important card on the screen)
> Build failures ↑28% · Sprint velocity decreasing · Authentication service becoming a bottleneck · Payments team overloaded · No security concerns
> Customer delivery risk: **Medium**
> Recommendations: 1) Move backend resources 2) Delay Feature X 3) Review dependency EPIC-443

One glance. One minute.

## AI everywhere

- **Ask AI** on every screen — an always-available copilot panel: *"Why is Sprint 12 delayed?"* → Explain · Show Evidence · Suggest Solution.
- **Natural-language search** instead of filter dropdowns: *"Why are payments delayed?" · "Projects with highest technical debt" · "Which project needs executive attention?"*
- **AI on every entity page.** An Issue page shows: AI Summary · Likely Root Cause · Related Issues · Duplicate Probability · Business Impact · Estimated Resolution · Suggested Owner · Affected Systems · Historical Similar Incidents.

## Explainability & confidence (trust)

Professionals love confidence scores. Every AI prediction shows a **Confidence %**, and every recommendation supports: **Why? · Evidence · Sources · Timeline · Related Issues · Historical Incidents · Affected Services · Prediction Confidence.** Trust comes from explainability.

## Visual language

- **Beautiful project cards**, not tables: Health % · Sprint % · Delivery % · Risk level + *"AI says: database migration dependency likely delays release" (Confidence 91%)*.
- **Timeline intelligence** — an interactive causal timeline (Build failed → Deployment delayed → API timeout → Customer complaint → Incident) ending in an **AI Conclusion**.
- **Dependency graph** — interactive, zoomable (Project → Epic → Story → Service → Database → Deployment → Customer).
- **Team health cards** — Focus · Interruptions · Meeting load · Burnout risk · Knowledge distribution · Delivery confidence (not just a velocity chart).
- **AI Risk Radar** per project (Security · Scheduling · Dependencies · Quality · Budget · Infrastructure · Technical Debt · Vendor · Compliance · Resources).
- **AI Heatmap** — projects colored Critical / Warning / Healthy / Stable, obvious at a glance.
- **Executive Dashboard** — Portfolio Health % · Budget Risk · Schedule Risk · Customer Impact · AI Overall Assessment · Predicted Quarter Success. Executives should never open Jira.

## Smart notifications (not "issue updated")

> **AI Alert:** Three independent bugs likely share the same root cause.
> **AI Alert:** Sprint completion probability dropped from 91% to 63%.
> **AI Alert:** Developer workload imbalance detected.

## AI analytics (executives love trends)

Delivery Forecast (current / next month / next quarter) · Release Confidence (Ready % · major risks · blocking issues · Go/No-Go) · Technical Debt trend + root cause · Team Efficiency (planning accuracy · delivery accuracy · rework · blocked time).

## Reports — interactive, not PDFs

Executive Report · Engineering Report · Program Health · AI Recommendations · Delivery/Incident/Budget trends · Risk Evolution · Velocity trends.

## Color philosophy

Avoid rainbow dashboards. Professional enterprise palette:

- **Base:** White · Light Gray · Dark Gray · **Navy** · **Azure Blue**
- **Status (small amounts only):** Orange · Red · Green
- **Never bright colors everywhere.**

## Typography

Large headings · lots of whitespace · very little text. **Executives scan; they don't read.**

## Premium UX details

Skeleton loaders (not spinners) · keyboard shortcuts · instant search · transitions < 200 ms · auto-save · **side panels instead of full-page reloads** · consistent empty states with suggested AI actions · rich hover previews · responsive on large monitors and laptops.

## The "wow" features

| Feature | Why it's compelling |
|---|---|
| AI Executive Briefing | Summarizes everything important in under a minute |
| AI Root-Cause Graph | Connects issues, services, deployments, incidents into a causal chain |
| Project Health Score | One explainable score from many signals |
| Release Success Prediction | Release outcome with confidence + evidence |
| Delivery Risk Forecast | Predicts schedule slippage before it happens |
| Organizational Knowledge Graph | Relationships among teams, projects, systems, dependencies |
| AI "What Changed?" Timeline | Meaningful changes across projects over any period |
| Digital Twin / Scenario Simulator | *"What happens if we delay Feature A by two weeks?"* |

## Notes — "Today's Attention" vs "Top projects by risk"

Two Mission sections that must stay conceptually distinct (they answer different questions):

| | **Today's Attention** | **Top projects by risk** |
|---|---|---|
| Question | *What do I act on now?* | *Which projects are worst overall?* |
| Grain | a **finding** (a specific risk item inside a project) | a **project** (one row each) |
| Ranking | **attention score** = severity × likelihood × **recency** (urgency) | cumulative **risk score** (blockers, reopen rate, aging) |
| Time | time-sensitive; changes daily ("Today's", with date history) | slow-moving / structural |
| Output | an **action queue** — each item has a next action | a **risk register** — triage list |
| A project appears | 0, 1, or **many** times (per finding), or not at all | exactly **once** |

The tell: a project can top the **register** (chronic accumulated debt) yet have **nothing** in Today's Attention (nothing urgent changed today); and a green project can top **Attention** because a critical finding just landed. One is *"where is the chronic risk"*; the other is *"where is the fire, and what do I do."*

To keep them from looking redundant: Attention leans on **recency + "new since yesterday"** and always carries the **recommended next action**; Top-projects carries a **trend arrow** (risk ↑/↓ vs last week) and stays project-grain. If they still feel duplicative on the home, move Top-projects to **Investigate** (browse the register) and keep Mission purely "what needs me now."

## The bigger vision

The strongest products here don't replace Jira — they treat Jira (and GitHub, Azure DevOps, ServiceNow, Slack/Teams, CI/CD, observability, docs) as **data sources**. What users experience is an **AI operational-intelligence platform** that answers questions, predicts outcomes, explains risks, and recommends actions — not just a place to manage tickets.

---

## Where the current build stands vs. this vision

**Have (real, working):** governed evidence pipeline, deterministic metrics, multi-agent risk analysis with **confidence + explanations + evidence**, live activity dashboard, portfolio (group) risk. This is the engine behind "AI Insights / Risks."

**Gap to close (UI-led, incremental):**
1. **Palette → navy/azure/neutral** (retire violet). *(highest impact, first)*
2. **Home → AI Executive Assistant** layout (greeting, hero stats + AI confidence, Today's Attention, AI Executive Summary). *(first)*
3. Scannable typography (large headings, whitespace, less text).
4. Confidence % + "why/evidence" surfaced on every finding.
5. Project **cards** with health/risk scores + "AI says…".
6. Minimal nav rename (Home / Projects / Risks / Dependencies / Teams / Analytics / Reports / Administration).
7. Then: risk radar, heatmap, causal timeline, dependency graph, NL search, Ask-AI copilot, scenario simulator.

Items 1–5 are achievable now against existing endpoints; 6–7 are the roadmap.
