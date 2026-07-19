import { DecimalPipe } from '@angular/common';
import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AnalysisRun, Report, RiskFinding } from '../models/analysis';
import { RiskAnalyticsService } from '../services/risk-analytics.service';

interface AgentOption {
  key: string;
  label: string;
  selected: boolean;
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

@Component({
  selector: 'app-project-risk',
  imports: [FormsModule, DecimalPipe],
  templateUrl: './project-risk.html',
  styleUrl: './project-risk.css',
})
export class ProjectRisk {
  protected projectKey = 'APACHE';
  protected includeReview = false;

  protected readonly agents = signal<AgentOption[]>(
    DETECTOR_AGENTS.map((a) => ({ key: a.key, label: a.label, selected: a.defaultOn })),
  );

  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly run = signal<AnalysisRun | null>(null);

  /** Findings sorted by score, highest first. */
  protected readonly sortedFindings = computed<RiskFinding[]>(() => {
    const current = this.run();
    if (!current) {
      return [];
    }
    return [...current.findings].sort((a, b) => b.score - a.score);
  });

  protected readonly reports = computed<Report[]>(() => this.run()?.reports ?? []);

  private readonly requestedBy = 'project-tracker-ui';

  constructor(private readonly riskService: RiskAnalyticsService) {}

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

  protected runAnalysis(): void {
    if (!this.canRun) {
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.run.set(null);

    this.riskService
      .startAnalysis(this.projectKey.trim(), {
        agents: this.selectedKeys,
        includeReview: this.includeReview,
        requestedBy: this.requestedBy,
      })
      .subscribe({
        next: (result) => {
          this.run.set(result);
          this.loading.set(false);
        },
        error: () => {
          this.error.set(
            'Unable to run the analysis. Is the RiskAnalytics-API running on :8004 ' +
              '(and is ANTHROPIC_API_KEY set)?',
          );
          this.loading.set(false);
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
}
