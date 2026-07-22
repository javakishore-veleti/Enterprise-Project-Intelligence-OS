import { TitleCasePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AnalysisRun, RiskFinding } from '../models/analysis';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';

const SEVERITY_RANK: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

@Component({
  selector: 'app-mission',
  imports: [RouterLink, TitleCasePipe],
  templateUrl: './mission.html',
  styleUrl: './mission.css',
})
export class Mission implements OnInit {
  private readonly riskService = inject(RiskAnalyticsService);
  private readonly projectsService = inject(ProjectsService);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  // Hero stats.
  protected readonly projectsMonitored = signal(0);
  protected readonly issuesAnalyzed = signal(0);
  protected readonly analysesRun = signal(0);
  protected readonly criticalRisks = signal(0);
  protected readonly aiConfidence = signal(0);

  // Today's Attention (the single most important finding, fully detailed).
  protected readonly attention = signal<{ finding: RiskFinding; run: AnalysisRun } | null>(null);

  // AI Executive Summary.
  protected readonly execFindings = signal<RiskFinding[]>([]);
  protected readonly execReportSummary = signal<string | null>(null);
  protected readonly deliveryRisk = signal<'Low' | 'Medium' | 'High'>('Low');

  protected readonly greeting = computed(() => {
    const h = new Date().getHours();
    return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  });
  protected readonly principal = 'Kishore';

  ngOnInit(): void {
    this.projectsService.searchProjects({ limit: 200 }).subscribe({
      next: (r) => {
        this.projectsMonitored.set(r.page.total);
        this.issuesAnalyzed.set(r.items.reduce((s, p) => s + (p.issue_count ?? 0), 0));
      },
      error: () => {},
    });

    this.riskService.getActivity(25).subscribe({
      next: (act) => {
        this.analysesRun.set(act.totals.total_runs);
        const findings = act.recent_findings ?? [];
        this.criticalRisks.set(
          findings.filter((f) => ['HIGH', 'CRITICAL'].includes((f.severity || '').toUpperCase())).length,
        );
        this.deliveryRisk.set(this.riskLevel(findings.map((f) => f.severity)));

        // Pick the most severe recent finding; load its full run for actions + confidence.
        const top = [...findings].sort(
          (a, b) => (SEVERITY_RANK[(b.severity || '').toUpperCase()] ?? 0) - (SEVERITY_RANK[(a.severity || '').toUpperCase()] ?? 0) || b.score - a.score,
        )[0];
        if (!top) { this.loading.set(false); return; }

        this.riskService.getRun(top.run_id).subscribe({
          next: (run) => {
            const full = run.findings.find((f) => f.finding_id === top.finding_id) ?? run.findings[0] ?? null;
            if (full) this.attention.set({ finding: full, run });
            // Exec summary: top findings of this run + its executive report.
            this.execFindings.set(
              [...run.findings].sort((a, b) => b.score - a.score).slice(0, 5),
            );
            const exec = run.reports?.find((rp) => (rp.kind || '').toLowerCase() === 'executive');
            this.execReportSummary.set(exec?.summary ?? null);
            const confs = run.findings.map((f) => f.confidence).filter((c) => typeof c === 'number');
            this.aiConfidence.set(confs.length ? Math.round((confs.reduce((s, c) => s + c, 0) / confs.length) * 100) : 0);
            this.loading.set(false);
          },
          error: () => this.loading.set(false),
        });
      },
      error: () => {
        this.error.set('Unable to reach the intelligence services. Are the APIs running on :8003/:8004?');
        this.loading.set(false);
      },
    });
  }

  private riskLevel(severities: string[]): 'Low' | 'Medium' | 'High' {
    const up = severities.map((s) => (s || '').toUpperCase());
    if (up.some((s) => s === 'CRITICAL' || s === 'HIGH')) return 'High';
    if (up.some((s) => s === 'MEDIUM')) return 'Medium';
    return 'Low';
  }

  protected severityClass(sev: string): string {
    return (sev || 'unknown').toLowerCase();
  }

  /** Probability of slip as a percent, from the finding's probability (0–1). */
  protected slipPct(f: RiskFinding): number {
    return Math.round((f.probability ?? 0) * 100);
  }

  protected confPct(f: RiskFinding): number {
    return Math.round((f.confidence ?? 0) * 100);
  }
}
