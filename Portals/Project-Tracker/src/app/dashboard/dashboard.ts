import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AttentionItem } from '../models/analysis';
import { ProjectMetrics } from '../models/project';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';
import { About } from '../ui/about';
import { UserScopeService } from '../ui/user-scope.service';

const SEVERITY_RANK: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
const FETCH = 100;

type SortKey = 'priority' | 'slip' | 'severity' | 'confidence' | 'recent' | 'project';
type SubView = 'attention' | 'progress' | 'agents';

interface MetricDef { key: keyof ProjectMetrics; label: string; kind: 'count' | 'pct' | 'days' | 'num'; }
const METRICS: ReadonlyArray<MetricDef> = [
  { key: 'blocker_count', label: 'Blockers', kind: 'count' },
  { key: 'reopen_rate', label: 'Reopen rate', kind: 'pct' },
  { key: 'resolution_velocity', label: 'Resolution velocity', kind: 'num' },
  { key: 'issue_aging_days', label: 'Issue aging', kind: 'days' },
  { key: 'critical_defect_ratio', label: 'Critical-defect ratio', kind: 'pct' },
  { key: 'backlog_growth', label: 'Backlog growth', kind: 'pct' },
  { key: 'contributor_concentration', label: 'Contributor concentration', kind: 'pct' },
];
const RANGES: ReadonlyArray<{ key: string; label: string; ms: number }> = [
  { key: '15m', label: 'Last 15 min', ms: 15 * 60e3 },
  { key: '1h', label: 'Last hour', ms: 60 * 60e3 },
  { key: '24h', label: 'Last 24 hours', ms: 24 * 3600e3 },
  { key: '7d', label: 'Last 7 days', ms: 7 * 864e5 },
  { key: '30d', label: 'Last 30 days', ms: 30 * 864e5 },
  { key: '6mo', label: 'Last 6 months', ms: 182 * 864e5 },
];

/** Detector + review agents from admin.agent_configs (the roster the platform runs). */
const AGENTS: ReadonlyArray<{ key: string; label: string; group: string }> = [
  { key: 'schedule_risk', label: 'Schedule Risk', group: 'Detectors' },
  { key: 'quality_risk', label: 'Quality Risk', group: 'Detectors' },
  { key: 'project_status_tracking', label: 'Project Status Tracking', group: 'Detectors' },
  { key: 'dependency_risk', label: 'Dependency Risk', group: 'Detectors' },
  { key: 'resource_risk', label: 'Resource Risk', group: 'Detectors' },
  { key: 'backlog_health', label: 'Backlog Health', group: 'Detectors' },
  { key: 'delivery_forecasting', label: 'Delivery Forecasting', group: 'Detectors' },
  { key: 'risk_scoring', label: 'Risk Scoring', group: 'Review' },
  { key: 'risk_deduplication', label: 'Risk Deduplication', group: 'Review' },
  { key: 'risk_correlation', label: 'Risk Correlation', group: 'Review' },
  { key: 'evidence_validation', label: 'Evidence Validation', group: 'Review' },
  { key: 'critic', label: 'Critic', group: 'Review' },
  { key: 'mitigation_planning', label: 'Mitigation Planning', group: 'Review' },
  { key: 'project_reporting', label: 'Project Reporting', group: 'Review' },
  { key: 'executive_reporting', label: 'Executive Reporting', group: 'Review' },
];

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, FormsModule, DecimalPipe, About],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard {
  private readonly risk = inject(RiskAnalyticsService);
  private readonly projectsSvc = inject(ProjectsService);
  protected readonly scope = inject(UserScopeService);

  protected subview: SubView = 'attention';
  protected readonly metricDefs = METRICS;
  protected readonly ranges = RANGES;
  protected readonly agentList = AGENTS;

  /** Projects in the current scope (for the selectors). */
  protected readonly scopeProjects = signal<string[]>([]);

  // ---- Attention workbench ----
  private readonly all = signal<AttentionItem[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected view: 'cards' | 'table' = 'cards';
  protected sortBy: SortKey = 'priority';
  protected topN = 10;
  protected asOf = '';
  protected readonly sorts: ReadonlyArray<{ key: SortKey; label: string }> = [
    { key: 'priority', label: 'AI priority (smart)' }, { key: 'slip', label: 'Slip likelihood' },
    { key: 'severity', label: 'Severity' }, { key: 'confidence', label: 'AI confidence' },
    { key: 'recent', label: 'Most recent' }, { key: 'project', label: 'Project' },
  ];
  protected readonly topOptions = [5, 10, 25, 50, 100];
  protected readonly todayStr = this.isoDate(0);

  protected readonly items = computed(() => [...this.all()].sort((a, b) => this.cmp(a, b)).slice(0, this.topN));

  // ---- Progress graph ----
  protected progProject = '';
  protected progMetric: keyof ProjectMetrics = 'blocker_count';
  protected progRange = '7d';
  private readonly progHistory = signal<ProjectMetrics[]>([]);
  protected readonly progLoading = signal(false);

  /** Points for the SVG chart within the selected range. */
  protected readonly progSeries = computed(() => {
    const rangeMs = RANGES.find((r) => r.key === this.progRange)?.ms ?? RANGES[3].ms;
    const cutoff = Date.now() - rangeMs;
    const rows = this.progHistory()
      .map((h) => ({ t: new Date(h.computed_at).getTime(), v: Number(h[this.progMetric] ?? 0) }))
      .filter((p) => !isNaN(p.t) && p.t >= cutoff)
      .sort((a, b) => a.t - b.t);
    if (rows.length === 0) return { pts: [], min: 0, max: 0, first: null, last: null, poly: '' };
    const vs = rows.map((r) => r.v);
    const min = Math.min(...vs), max = Math.max(...vs);
    const tMin = rows[0].t, tMax = rows[rows.length - 1].t;
    const W = 640, H = 180, pad = 8;
    const x = (t: number) => tMax === tMin ? W / 2 : pad + (t - tMin) / (tMax - tMin) * (W - 2 * pad);
    const y = (v: number) => max === min ? H / 2 : H - pad - (v - min) / (max - min) * (H - 2 * pad);
    const pts = rows.map((r) => ({ x: x(r.t), y: y(r.v), v: r.v, t: r.t }));
    return { pts, min, max, first: rows[0], last: rows[rows.length - 1], poly: pts.map((p) => `${p.x},${p.y}`).join(' ') };
  });

  // ---- Agents outcomes ----
  protected agentKey = 'schedule_risk';
  private readonly agentFindings = signal<AttentionItem[]>([]);
  protected readonly agentOutcome = computed(() => {
    const mine = this.agentFindings().filter((f) => f.agent_key === this.agentKey);
    const bySev = { critical: 0, high: 0, medium: 0, low: 0 } as Record<string, number>;
    const byProj: Record<string, number> = {};
    for (const f of mine) {
      const s = (f.severity || '').toLowerCase(); if (s in bySev) bySev[s]++;
      byProj[f.project_key] = (byProj[f.project_key] ?? 0) + 1;
    }
    const projects = Object.entries(byProj).sort((a, b) => b[1] - a[1]).slice(0, 8);
    return { count: mine.length, bySev, projects };
  });

  constructor() {
    toObservable(this.scope.userKey).subscribe(() => this.reloadScope());
  }

  private reloadScope(): void {
    const userKey = this.scope.userKey();
    if (userKey) {
      this.projectsSvc.getPortfolioSummary(50, userKey).subscribe({
        next: (s) => { const keys = s.top_projects.map((p) => p.project_key); this.applyScope(keys); },
        error: () => this.applyScope(undefined),
      });
    } else {
      // Unscoped: fetch a project list for the selectors.
      this.projectsSvc.searchProjects({ limit: 50 }).subscribe({
        next: (r) => this.applyScope(r.items.map((p) => p.project_key)),
        error: () => this.applyScope(undefined),
      });
    }
  }

  private applyScope(keys: string[] | undefined): void {
    this.scopeProjects.set(keys ?? []);
    if (keys?.length && !keys.includes(this.progProject)) this.progProject = keys[0];
    this.reloadAttention(keys);
    if (this.subview === 'progress') this.loadHistory();
  }

  // Attention data
  private reloadAttention(projects?: string[]): void {
    this.loading.set(true); this.error.set(null);
    this.risk.getAttention(FETCH, { asOf: this.asOf || undefined, projects }).subscribe({
      next: (r) => { this.all.set(r.items); this.agentFindings.set(r.items); this.total.set(r.total); this.loading.set(false); },
      error: () => { this.error.set('Unable to load the attention feed. Is the RiskAnalytics-API running on :8004?'); this.loading.set(false); },
    });
  }

  protected onDateChange(): void { this.reloadAttention(this.scopeProjects().length ? this.scopeProjects() : undefined); }
  protected setToday(): void { this.asOf = ''; this.onDateChange(); }
  protected setYesterday(): void { this.asOf = this.isoDate(-1); this.onDateChange(); }
  protected get isToday(): boolean { return this.asOf === '' || this.asOf === this.todayStr; }

  protected setSub(v: SubView): void {
    this.subview = v;
    if (v === 'progress' && this.progProject) this.loadHistory();
  }

  protected loadHistory(): void {
    if (!this.progProject) return;
    this.progLoading.set(true);
    this.projectsSvc.getMetricsHistory(this.progProject, 300).subscribe({
      next: (r) => { this.progHistory.set(r.history ?? []); this.progLoading.set(false); },
      error: () => { this.progHistory.set([]); this.progLoading.set(false); },
    });
  }

  private cmp(a: AttentionItem, b: AttentionItem): number {
    switch (this.sortBy) {
      case 'slip': return (b.probability ?? 0) - (a.probability ?? 0);
      case 'confidence': return (b.confidence ?? 0) - (a.confidence ?? 0);
      case 'severity': return (SEVERITY_RANK[(b.severity || '').toUpperCase()] ?? 0) - (SEVERITY_RANK[(a.severity || '').toUpperCase()] ?? 0) || b.attention_score - a.attention_score;
      case 'recent': return new Date(b.analysis_timestamp).getTime() - new Date(a.analysis_timestamp).getTime();
      case 'project': return a.project_key.localeCompare(b.project_key);
      default: return b.attention_score - a.attention_score;
    }
  }

  protected fmt(v: number, kind: string): string {
    if (kind === 'pct') return `${Math.round(v * 100)}%`;
    if (kind === 'days') return `${Math.round(v)}d`;
    if (kind === 'count') return `${Math.round(v)}`;
    return `${Math.round(v * 100) / 100}`;
  }
  protected metricKind(): string { return METRICS.find((m) => m.key === this.progMetric)?.kind ?? 'num'; }
  protected metricLabel(): string { return METRICS.find((m) => m.key === this.progMetric)?.label ?? ''; }
  protected tickDate(t: number): string { return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); }

  protected severityClass(sev: string): string { return (sev || 'unknown').toLowerCase(); }
  protected pctOf(v: number): number { return Math.round((v ?? 0) * 100); }
  protected primaryAction(a: AttentionItem): string | null { return a.recommended_actions?.[0] ?? null; }
  protected ago(iso: string): string {
    const then = new Date(iso).getTime(); if (isNaN(then)) return '';
    const s = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (s < 60) return `${s}s ago`; const m = Math.round(s / 60); if (m < 60) return `${m}m ago`;
    const h = Math.round(m / 60); if (h < 24) return `${h}h ago`; return `${Math.round(h / 24)}d ago`;
  }
  private isoDate(days: number): string { const d = new Date(); d.setDate(d.getDate() + days); return d.toISOString().slice(0, 10); }
}
