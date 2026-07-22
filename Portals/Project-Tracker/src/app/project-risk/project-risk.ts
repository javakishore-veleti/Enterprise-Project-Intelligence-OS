import { HttpErrorResponse } from '@angular/common/http';
import { DecimalPipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { AnalysisRun, AnalysisRunSummary, Report, RiskFinding } from '../models/analysis';
import { ProjectMetrics } from '../models/project';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';
import { About } from '../ui/about';
import { NotificationService } from '../ui/notification.service';

interface AgentOption {
  key: string;
  label: string;
  selected: boolean;
}

/** One label/value tile in the computed-metrics grid. */
interface MetricTile {
  label: string;
  value: string;
}

/** Per-agent rollup derived client-side from a run's findings. */
interface AgentBreakdownRow {
  agent_key: string;
  count: number;
  max_severity: string;
}

const DETECTOR_AGENTS: ReadonlyArray<{ key: string; label: string; defaultOn: boolean }> = [
  { key: 'schedule_risk', label: 'Schedule risk', defaultOn: true },
  { key: 'quality_risk', label: 'Quality risk', defaultOn: true },
  { key: 'project_status_tracking', label: 'Project status tracking', defaultOn: false },
  { key: 'dependency_risk', label: 'Dependency risk', defaultOn: false },
  { key: 'resource_risk', label: 'Resource risk', defaultOn: false },
  { key: 'backlog_health', label: 'Backlog health', defaultOn: false },
  { key: 'delivery_forecasting', label: 'Delivery forecasting', defaultOn: false },
];

/** Severity ordering (high → low) for the per-agent max-severity rollup. */
const SEVERITY_RANK: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

@Component({
  selector: 'app-project-risk',
  imports: [FormsModule, DecimalPipe, About],
  templateUrl: './project-risk.html',
  styleUrl: './project-risk.css',
})
export class ProjectRisk implements OnInit {
  protected projectKey = 'APACHE';
  protected includeReview = false;

  protected readonly agents = signal<AgentOption[]>(
    DETECTOR_AGENTS.map((a) => ({ key: a.key, label: a.label, selected: a.defaultOn })),
  );

  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly run = signal<AnalysisRun | null>(null);

  // Computed metrics panel.
  protected readonly metrics = signal<ProjectMetrics | null>(null);
  protected readonly metricsLoading = signal(false);
  protected readonly metricsMissing = signal(false);
  protected readonly metricsError = signal<string | null>(null);

  // Analysis history.
  protected readonly runs = signal<AnalysisRunSummary[]>([]);
  protected readonly historyLoading = signal(false);
  protected readonly historyError = signal<string | null>(null);
  protected readonly runLoading = signal(false);

  /** Findings sorted by score, highest first. */
  protected readonly sortedFindings = computed<RiskFinding[]>(() => {
    const current = this.run();
    if (!current) {
      return [];
    }
    return [...current.findings].sort((a, b) => b.score - a.score);
  });

  protected readonly reports = computed<Report[]>(() => this.run()?.reports ?? []);

  /** Per-agent execution breakdown derived from the current run's findings. */
  protected readonly agentBreakdown = computed<AgentBreakdownRow[]>(() => {
    const current = this.run();
    if (!current) {
      return [];
    }
    const byAgent = new Map<string, AgentBreakdownRow>();
    for (const finding of current.findings) {
      const key = finding.agent_key;
      const severity = (finding.severity || 'UNKNOWN').toUpperCase();
      const existing = byAgent.get(key);
      if (!existing) {
        byAgent.set(key, { agent_key: key, count: 1, max_severity: severity });
      } else {
        existing.count += 1;
        if ((SEVERITY_RANK[severity] ?? 0) > (SEVERITY_RANK[existing.max_severity] ?? 0)) {
          existing.max_severity = severity;
        }
      }
    }
    return [...byAgent.values()].sort((a, b) => b.count - a.count);
  });

  /** Metrics rendered as label/value tiles with sensible formatting. */
  protected readonly metricTiles = computed<MetricTile[]>(() => {
    const m = this.metrics();
    if (!m) {
      return [];
    }
    return [
      { label: 'Backlog growth', value: this.asPercent(m.backlog_growth) },
      { label: 'Reopen rate', value: this.asPercent(m.reopen_rate) },
      { label: 'Blocker count', value: this.asCount(m.blocker_count) },
      { label: 'Dependency depth', value: this.asCount(m.dependency_depth) },
      { label: 'Issue aging', value: this.asDays(m.issue_aging_days) },
      { label: 'Resolution velocity', value: this.asNumber(m.resolution_velocity) },
      { label: 'Contributor concentration', value: this.asPercent(m.contributor_concentration) },
      { label: 'Critical defect ratio', value: this.asPercent(m.critical_defect_ratio) },
    ];
  });

  private readonly requestedBy = 'project-tracker-ui';

  private readonly route = inject(ActivatedRoute);
  private readonly notify = inject(NotificationService);

  constructor(
    private readonly riskService: RiskAnalyticsService,
    private readonly projectsService: ProjectsService,
  ) {}

  ngOnInit(): void {
    // Prefill + auto-load when arriving from a project's "Analyze →" link.
    this.route.queryParamMap.subscribe((params) => {
      const key = params.get('project');
      if (key && key.trim().length > 0) {
        this.projectKey = key.trim();
        this.loadProjectContext();
      }
    });
  }

  protected toggleAgent(key: string): void {
    this.agents.update((list) =>
      list.map((a) => (a.key === key ? { ...a, selected: !a.selected } : a)),
    );
  }

  protected get selectedKeys(): string[] {
    return this.agents()
      .filter((a) => a.selected)
      .map((a) => a.key);
  }

  protected get canRun(): boolean {
    return !this.loading() && this.projectKey.trim().length > 0 && this.selectedKeys.length > 0;
  }

  /** Load the computed metrics + run history for the current project key. */
  protected loadProjectContext(): void {
    const key = this.projectKey.trim();
    if (key.length === 0) {
      return;
    }
    this.loadMetrics(key);
    this.loadHistory(key);
  }

  private loadMetrics(key: string): void {
    this.metricsLoading.set(true);
    this.metricsMissing.set(false);
    this.metricsError.set(null);
    this.projectsService.getProjectMetrics(key).subscribe({
      next: (result) => {
        this.metrics.set(result);
        this.metricsLoading.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.metrics.set(null);
        this.metricsMissing.set(err.status === 404);
        this.metricsError.set(
          err.status === 404
            ? null
            : 'Unable to load metrics. Is the Projects-API running on :8003?',
        );
        this.metricsLoading.set(false);
      },
    });
  }

  private loadHistory(key: string): void {
    this.historyLoading.set(true);
    this.historyError.set(null);
    this.riskService.listRuns(key, 20).subscribe({
      next: (result) => {
        this.runs.set(result.runs);
        this.historyLoading.set(false);
      },
      error: () => {
        this.runs.set([]);
        this.historyError.set('Unable to load analysis history. Is the RiskAnalytics-API running on :8004?');
        this.historyLoading.set(false);
      },
    });
  }

  protected async runAnalysis(): Promise<void> {
    if (!this.canRun) {
      return;
    }
    const key = this.projectKey.trim();
    const count = this.selectedKeys.length;
    const confirmed = await this.notify.confirm({
      title: 'Run risk analysis?',
      message:
        `This runs ${count} detector agent${count === 1 ? '' : 's'} on ${key}` +
        (this.includeReview ? ' plus the full review pipeline' : '') +
        ' via live LLM calls, and may take 30–60s.',
      confirmLabel: 'Run analysis',
    });
    if (!confirmed) {
      return;
    }

    this.loading.set(true);
    this.error.set(null);
    this.run.set(null);
    this.notify.info('Analysis started', `${count} agent${count === 1 ? '' : 's'} on ${key} — this can take up to a minute.`);
    // Refresh the metrics panel alongside the analysis.
    this.loadMetrics(key);

    this.riskService
      .startAnalysis(key, {
        agents: this.selectedKeys,
        includeReview: this.includeReview,
        requestedBy: this.requestedBy,
      })
      .subscribe({
        next: (result) => {
          this.run.set(result);
          this.loading.set(false);
          this.notify.success(
            'Analysis complete',
            `${result.findings.length} finding${result.findings.length === 1 ? '' : 's'} · ${result.reports?.length ?? 0} report${(result.reports?.length ?? 0) === 1 ? '' : 's'} for ${key}.`,
          );
          // Reflect the just-completed run in the history table.
          this.loadHistory(key);
        },
        error: () => {
          this.error.set(
            'Unable to run the analysis. Is the RiskAnalytics-API running on :8004 ' +
              '(and is ANTHROPIC_API_KEY set)?',
          );
          this.notify.error('Analysis failed', 'The RiskAnalytics-API did not respond. Check :8004 and ANTHROPIC_API_KEY.');
          this.loading.set(false);
        },
      });
  }

  /** Load a full run (findings + reports) from a history row's "View" action. */
  protected viewRun(runId: string): void {
    this.runLoading.set(true);
    this.error.set(null);
    this.riskService.getRun(runId).subscribe({
      next: (result) => {
        this.run.set(result);
        this.runLoading.set(false);
      },
      error: () => {
        this.error.set('Unable to load that run. Is the RiskAnalytics-API running on :8004?');
        this.runLoading.set(false);
      },
    });
  }

  /** Severity → lowercased css-modifier token (e.g. "CRITICAL" → "critical"). */
  protected severityClass(severity: string): string {
    return (severity || 'unknown').toLowerCase();
  }

  protected priorityRank(finding: RiskFinding): number | null {
    return this.numberMeta(finding, 'priority_rank');
  }

  protected mergedCount(finding: RiskFinding): number | null {
    return this.numberMeta(finding, 'merged_count');
  }

  protected criticVerdict(finding: RiskFinding): string | null {
    const value = finding.meta?.['critic_verdict'];
    return typeof value === 'string' ? value : null;
  }

  private numberMeta(finding: RiskFinding, key: string): number | null {
    const value = finding.meta?.[key];
    return typeof value === 'number' ? value : null;
  }

  private asPercent(value: number): string {
    return `${(value * 100).toFixed(1)}%`;
  }

  private asCount(value: number): string {
    return `${Math.round(value)}`;
  }

  private asDays(value: number): string {
    return `${Math.round(value)}d`;
  }

  private asNumber(value: number): string {
    return value.toFixed(2);
  }
}
