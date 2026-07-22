import { DecimalPipe, TitleCasePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AnalysisRun, RiskFinding } from '../models/analysis';
import { PortfolioProject, PortfolioSummary } from '../models/portfolio';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';

const SEVERITY_RANK: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

/** Demo identities (seam for real SSO). Keys match the seeded project_assignments. */
const USERS: ReadonlyArray<{ key: string; label: string }> = [
  { key: '', label: 'Director — all projects' },
  { key: 'mgr-apac', label: 'APAC Delivery Manager' },
  { key: 'mgr-data', label: 'Data Platform Manager' },
];

@Component({
  selector: 'app-mission',
  imports: [RouterLink, FormsModule, TitleCasePipe, DecimalPipe],
  templateUrl: './mission.html',
  styleUrl: './mission.css',
})
export class Mission implements OnInit {
  private readonly projectsService = inject(ProjectsService);
  private readonly riskService = inject(RiskAnalyticsService);

  protected readonly users = USERS;
  protected currentUser = '';

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly summary = signal<PortfolioSummary | null>(null);

  // Today's Attention — detail for the single riskiest project (scoped, 1 project).
  protected readonly attention = signal<{ finding: RiskFinding; run: AnalysisRun } | null>(null);
  protected readonly aiConfidence = signal(0);
  protected readonly execReportSummary = signal<string | null>(null);

  protected readonly topProjects = computed(() => this.summary()?.top_projects ?? []);
  protected readonly greeting = computed(() => {
    const h = new Date().getHours();
    return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  });

  ngOnInit(): void {
    this.load();
  }

  protected onUserChange(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.attention.set(null);
    this.execReportSummary.set(null);
    this.aiConfidence.set(0);

    this.projectsService.getPortfolioSummary(15, this.currentUser || null).subscribe({
      next: (s) => {
        this.summary.set(s);
        const top = s.top_projects[0];
        if (!top) { this.loading.set(false); return; }
        this.loadAttention(top.project_key);
      },
      error: () => {
        this.error.set('Unable to load your portfolio. Is the Projects-API running on :8003?');
        this.loading.set(false);
      },
    });
  }

  /** Rich Today's Attention detail for one project (its latest run) — scoped, cheap. */
  private loadAttention(projectKey: string): void {
    this.riskService.listRuns(projectKey, 1).subscribe({
      next: (r) => {
        const runId = r.runs[0]?.run_id;
        if (!runId) { this.loading.set(false); return; }
        this.riskService.getRun(runId).subscribe({
          next: (run) => {
            const top = [...run.findings].sort((a, b) => b.score - a.score)[0] ?? null;
            if (top) this.attention.set({ finding: top, run });
            const exec = run.reports?.find((rp) => (rp.kind || '').toLowerCase() === 'executive');
            this.execReportSummary.set(exec?.summary ?? null);
            const confs = run.findings.map((f) => f.confidence).filter((c) => typeof c === 'number');
            this.aiConfidence.set(confs.length ? Math.round((confs.reduce((s, c) => s + c, 0) / confs.length) * 100) : 0);
            this.loading.set(false);
          },
          error: () => this.loading.set(false),
        });
      },
      error: () => this.loading.set(false),
    });
  }

  protected bandClass(band: string): string {
    return (band || 'low').toLowerCase();
  }
  protected severityClass(sev: string): string {
    return (sev || 'unknown').toLowerCase();
  }
  protected scoreClass(score: number): string {
    return score >= 66 ? 'high' : score >= 33 ? 'medium' : 'low';
  }
  protected slipPct(f: RiskFinding): number {
    return Math.round((f.probability ?? 0) * 100);
  }
  protected confPct(f: RiskFinding): number {
    return Math.round((f.confidence ?? 0) * 100);
  }
  protected pct(v: number): string {
    return `${Math.round(v * 100)}%`;
  }
  protected roundedDays(v: number): number {
    return Math.round(v);
  }
}
