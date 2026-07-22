import { Component, computed, effect, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { map } from 'rxjs/operators';

import { About } from '../ui/about';

/** One agent row in a verb's "agents available" table. */
interface HelpAgent {
  name: string;
  key: string;
  type: string;       // Detector · Review · Orchestrator · Investigator · Forecaster
  framework: string;  // LangGraph (model choice is independent)
  role: string;       // one-line what it does
}

/** The full explainer for one verb. */
interface HelpTopic {
  key: Topic;
  title: string;
  whatItIs: string;
  providesLabel: string;
  provides: string[];
  data: string[];
  agents: HelpAgent[];
}

type Topic = 'mission' | 'watch' | 'investigate' | 'predict' | 'decide';

const ORDER: Topic[] = ['mission', 'watch', 'investigate', 'predict', 'decide'];

/** One-line essence of each verb, used to auto-generate the "how it differs" section. */
const ESSENCE: Record<Topic, { verb: string; phrase: string }> = {
  mission: { verb: 'Mission', phrase: 'surfaces what needs your attention now' },
  watch: { verb: 'Watch', phrase: 'tracks what changed and what is moving over time' },
  investigate: { verb: 'Investigate', phrase: 'explains why it is happening (root cause)' },
  predict: { verb: 'Predict', phrase: 'projects what will happen next (a forecast you review)' },
  decide: { verb: 'Decide', phrase: 'prescribes what to do and acts on it (with approval)' },
};

// Shared agent catalog (the platform's LangGraph roster) — referenced per verb.
const A: Record<string, HelpAgent> = {
  schedule: { name: 'Schedule Risk', key: 'schedule_risk', type: 'Detector', framework: 'LangGraph', role: 'Timeline slippage from velocity, aging and throughput' },
  quality: { name: 'Quality Risk', key: 'quality_risk', type: 'Detector', framework: 'LangGraph', role: 'Reopen churn and critical-defect ratio' },
  status: { name: 'Project Status Tracking', key: 'project_status_tracking', type: 'Detector', framework: 'LangGraph', role: 'Status distribution and delivery health' },
  dependency: { name: 'Dependency Risk', key: 'dependency_risk', type: 'Detector', framework: 'LangGraph', role: 'Blocking links and dependency depth' },
  resource: { name: 'Resource Risk', key: 'resource_risk', type: 'Detector', framework: 'LangGraph', role: 'Contributor concentration / bus-factor' },
  backlog: { name: 'Backlog Health', key: 'backlog_health', type: 'Detector', framework: 'LangGraph', role: 'Backlog growth and issue aging' },
  forecasting: { name: 'Delivery Forecasting', key: 'delivery_forecasting', type: 'Forecaster', framework: 'LangGraph', role: 'Completion / slip projection over trajectory' },
  scoring: { name: 'Risk Scoring', key: 'risk_scoring', type: 'Review', framework: 'Deterministic', role: 'Ranks findings by severity × probability × confidence' },
  dedup: { name: 'Risk Deduplication', key: 'risk_deduplication', type: 'Review', framework: 'Deterministic', role: 'Merges duplicate findings' },
  correlation: { name: 'Risk Correlation', key: 'risk_correlation', type: 'Review', framework: 'Deterministic', role: 'Groups related findings and shared causes' },
  evidence: { name: 'Evidence Validation', key: 'evidence_validation', type: 'Review', framework: 'LangGraph', role: 'Checks each finding is grounded in evidence' },
  critic: { name: 'Critic', key: 'critic', type: 'Review', framework: 'LangGraph', role: 'Adversarially challenges findings until they converge' },
  mitigation: { name: 'Mitigation Planning', key: 'mitigation_planning', type: 'Reporter', framework: 'LangGraph', role: 'Drafts concrete mitigation actions' },
  projectReport: { name: 'Project Reporting', key: 'project_reporting', type: 'Reporter', framework: 'LangGraph', role: 'Narrative report for a single project' },
  execReport: { name: 'Executive Reporting', key: 'executive_reporting', type: 'Reporter', framework: 'LangGraph', role: 'Portfolio-level executive summary' },
  manager: { name: 'Project Risk Manager', key: 'project_risk_manager', type: 'Orchestrator', framework: 'LangGraph', role: 'Coordinates the specialist fan-out and review pipeline' },
  investigator: { name: 'Investigation Agent', key: 'investigation', type: 'Investigator', framework: 'LangGraph', role: 'Tool-using root-cause investigation over the evidence store' },
  forecast: { name: 'Forecast Agent', key: 'forecast', type: 'Forecaster', framework: 'LangGraph', role: 'On-time probability + credible interval + drivers' },
  scenario: { name: 'Scenario Simulator', key: 'scenario', type: 'Forecaster', framework: 'LangGraph', role: 'What-if re-forecast with dependency cascade' },
  earlyWarning: { name: 'Early-Warning', key: 'early_warning', type: 'Monitor', framework: 'Deterministic', role: 'Detects adverse trajectory inflections' },
};

const HELP: Record<Topic, HelpTopic> = {
  mission: {
    key: 'mission', title: 'Mission',
    whatItIs: 'Your AI executive-assistant home. Mission is scoped to the projects you own and answers, in one glance, what most needs your attention right now — the vital few, not everything.',
    providesLabel: 'What insights it provides',
    provides: [
      'A portfolio risk score and High / Medium / Low band roll-up for your scope',
      'Today’s Attention — the top items ranked server-side by an attention score',
      'An AI executive summary of the last 24 hours with ranked recommendations',
    ],
    data: ['Computed project_metrics (Mongo)', 'Ranked findings (Postgres risk store)', 'Your project assignments (scope)'],
    agents: [A['execReport'], A['projectReport'], A['scoring'], A['manager']],
  },
  watch: {
    key: 'watch', title: 'Watch',
    whatItIs: 'The signals-and-attention workbench: what changed and what the detectors are surfacing. Watch is where you monitor movement — attention feed, a progress graph over time, and per-agent outcomes.',
    providesLabel: 'What metrics & signals it provides',
    provides: [
      'A ranked attention feed (today, yesterday, or any past date)',
      'A progress graph of a metric over time (15 min → 6 months)',
      'Per-agent outcomes: findings count, severity, and per-project breakdown',
    ],
    data: ['Computed project_metrics + metrics history (Mongo)', 'Findings and analysis runs (Postgres)', 'Attention snapshots by date'],
    agents: [A['schedule'], A['quality'], A['status'], A['backlog'], A['dependency'], A['resource'], A['scoring']],
  },
  investigate: {
    key: 'investigate', title: 'Investigate',
    whatItIs: 'The autonomous Investigation Agent. It decides which projects most need attention, forms hypotheses, calls evidence-store tools, and concludes with a root cause, confidence, and the exact evidence it used — which you can inspect and argue with.',
    providesLabel: 'What the agents do',
    provides: [
      'A root-cause conclusion with a causal chain and a confidence score',
      'A step-by-step reasoning trace, each step grounded in a tool call',
      'Cited evidence — the exact records behind the conclusion',
    ],
    data: ['Evidence store: issues, histories, links, contributors (Mongo)', 'Computed project_metrics', 'Persisted investigations (Postgres)'],
    agents: [A['investigator'], A['critic'], A['correlation'], A['evidence'], A['quality'], A['dependency'], A['resource']],
  },
  predict: {
    key: 'predict', title: 'Predict',
    whatItIs: 'What will happen next. Predict makes a forecast you review — an outcome with a credible interval and its drivers — plus a Digital-Twin what-if simulator and proactive early-warnings. It projects and explores; it never commits an action (that is Decide).',
    providesLabel: 'What forecasts it provides',
    provides: [
      'A delivery forecast: on-time probability ± a credible interval, with drivers',
      'A Digital-Twin what-if that re-forecasts and propagates impact along dependencies',
      'Proactive early-warnings when a trajectory inflects for the worse',
    ],
    data: ['Metric-history time series (Mongo)', 'Dependency links + shared-contributor graph', 'Persisted forecasts / scenarios (Postgres)'],
    agents: [A['forecast'], A['scenario'], A['earlyWarning'], A['forecasting'], A['dependency']],
  },
  decide: {
    key: 'decide', title: 'Decide',
    whatItIs: 'What you should do about it. Decide turns a chosen direction into a recommended, executable action plan — prioritized actions, suggested owners, options with trade-offs — that you approve and it acts on. It prescribes and commits (Predict only projected).',
    providesLabel: 'What actions it provides',
    provides: [
      'A drafted action plan: prioritized actions, suggested owners, estimated recovery',
      'Options with predicted outcomes and trade-offs to choose between',
      'On approval, it enacts the plan (e.g. creates the tickets)',
    ],
    data: ['Findings + mitigations (Postgres risk store)', 'Contributor data for owner suggestions', 'Computed project_metrics'],
    agents: [A['mitigation'], A['scoring'], A['dedup'], A['execReport'], A['manager']],
  },
};

/**
 * Help = per-verb explainer pages. Each has a consistent structure (what it is,
 * what it provides, what data it uses) and a searchable, client-paginated table
 * of the agents available for that context.
 */
@Component({
  selector: 'app-help',
  imports: [RouterLink, FormsModule, About],
  templateUrl: './help.html',
  styleUrl: './help.css',
})
export class Help {
  private readonly route = inject(ActivatedRoute);

  protected readonly topic = toSignal(
    this.route.queryParamMap.pipe(
      map((p) => {
        const v = p.get('v') as Topic | null;
        return v && HELP[v] ? v : 'mission';
      }),
    ),
    { initialValue: 'mission' as Topic },
  );

  protected readonly info = computed(() => HELP[this.topic()]);
  protected readonly heading = computed(() => `Help · ${this.info().title}`);
  protected readonly isPredictOrDecide = computed(() => this.topic() === 'predict' || this.topic() === 'decide');

  /** How the current verb differs from each of the other left-nav views. */
  protected readonly differs = computed(() => {
    const cur = this.topic();
    return ORDER.filter((t) => t !== cur).map((t) => ({
      verb: ESSENCE[t].verb,
      link: t,
      line: `${ESSENCE[cur].verb} ${ESSENCE[cur].phrase}, whereas ${ESSENCE[t].verb} ${ESSENCE[t].phrase}.`,
    }));
  });

  /** Table-of-contents entries for the current page. */
  protected readonly toc = computed(() => {
    const entries = [
      { id: 'what-it-is', label: 'What it is' },
      { id: 'provides', label: this.info().providesLabel },
      { id: 'data', label: 'What data it uses' },
      { id: 'differs', label: 'How it differs from the other views' },
      { id: 'agents', label: 'Agents available for this context' },
    ];
    if (this.isPredictOrDecide()) entries.push({ id: 'compare', label: 'Predict vs. Decide' });
    return entries;
  });

  // --- agents table: search + client pagination (10/page, max 100) ---
  protected readonly search = signal('');
  protected readonly page = signal(0);
  protected readonly pageSize = 10;
  protected readonly maxRows = 100;

  /** Agents for the current verb, hard-capped at 100. */
  private readonly capped = computed(() => this.info().agents.slice(0, this.maxRows));

  /** After the free-text filter (searches every column). */
  protected readonly filtered = computed(() => {
    const q = this.search().trim().toLowerCase();
    if (!q) return this.capped();
    return this.capped().filter((a) =>
      `${a.name} ${a.key} ${a.type} ${a.framework} ${a.role}`.toLowerCase().includes(q),
    );
  });

  protected readonly total = computed(() => this.filtered().length);
  protected readonly pageCount = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize)));
  protected readonly paged = computed(() => {
    const start = this.page() * this.pageSize;
    return this.filtered().slice(start, start + this.pageSize);
  });
  protected readonly pageStart = computed(() => (this.total() === 0 ? 0 : this.page() * this.pageSize + 1));
  protected readonly pageEnd = computed(() => Math.min((this.page() + 1) * this.pageSize, this.total()));

  constructor() {
    // Reset to page 0 whenever the verb or the search term changes.
    effect(() => {
      this.topic();
      this.search();
      this.page.set(0);
    });
  }

  protected prevPage(): void { if (this.page() > 0) this.page.update((p) => p - 1); }
  protected nextPage(): void { if (this.page() < this.pageCount() - 1) this.page.update((p) => p + 1); }

  /** The Predict-vs-Decide comparison, row by row (shown on those two topics). */
  protected readonly rows = [
    { dim: 'Question', predict: '“What will happen?”', decide: '“What should we do?”' },
    { dim: 'Output', predict: 'A forecast / projection — outcome + credible interval + drivers', decide: 'A plan / decision — prioritized actions, owners, options' },
    { dim: 'Stance', predict: 'Descriptive, exploratory — no commitment', decide: 'Prescriptive, committed — approve & act' },
    { dim: 'Scenario handling', predict: 'Digital-Twin what-if: “IF you did X → predicted future state + cascade + uncertainty” (a sandbox)', decide: 'Decision options: “Here are the recommended actions, trade-offs — pick one and I’ll execute it” (a proposal)' },
    { dim: 'Grounded in', predict: 'Trajectory / metric-history forecasting', decide: 'Interventions / mitigations (which lever to pull)' },
    { dim: 'Ends with', predict: 'A confidence-scored prediction you review', decide: 'A ticket created / owner assigned (with approval)' },
  ];
}
