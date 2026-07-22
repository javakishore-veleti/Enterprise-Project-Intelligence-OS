import { DecimalPipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { RecentFinding } from '../models/analysis';
import { PortfolioSummary } from '../models/portfolio';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';

const SEVERITY_WEIGHT: Record<string, number> = { CRITICAL: 1.0, HIGH: 0.8, MEDIUM: 0.5, LOW: 0.25 };

/** Demo identities (seam for real SSO). Keys match the seeded project_assignments. */
const USERS: ReadonlyArray<{ key: string; label: string }> = [
  { key: '', label: 'Director — all projects' },
  { key: 'mgr-apac', label: 'APAC Delivery Manager' },
  { key: 'mgr-data', label: 'Data Platform Manager' },
];

/** An attention item ranked for the feed (interim source: recent findings). */
interface AttentionItem extends RecentFinding {
  attention_score: number;
}

@Component({
  selector: 'app-mission',
  imports: [RouterLink, FormsModule, DecimalPipe],
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

  // Today's Attention — ranked top-N feed (scoped to the current user).
  protected readonly attention = signal<AttentionItem[]>([]);
  protected readonly attentionTotal = signal(0);

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
    this.attention.set([]);
    this.attentionTotal.set(0);

    this.projectsService.getPortfolioSummary(15, this.currentUser || null).subscribe({
      next: (s) => {
        this.summary.set(s);
        this.loadAttention(s);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load your portfolio. Is the Projects-API running on :8003?');
        this.loading.set(false);
      },
    });
  }

  /**
   * Build the ranked Top-10 attention feed. Interim source = recent findings,
   * scoped to the current user's projects and ranked by attention score.
   * (Swaps to the server-side /analysis/attention endpoint when live.)
   */
  private loadAttention(s: PortfolioSummary): void {
    const scopeKeys = s.scope?.scoped ? new Set(s.top_projects.map((p) => p.project_key)) : null;
    this.riskService.getActivity(50).subscribe({
      next: (act) => {
        let findings = act.recent_findings ?? [];
        if (scopeKeys) findings = findings.filter((f) => scopeKeys.has(f.project_key));
        const ranked = findings
          .map((f) => ({ ...f, attention_score: this.score(f) }))
          .sort((a, b) => b.attention_score - a.attention_score);
        this.attentionTotal.set(ranked.length);
        this.attention.set(ranked.slice(0, 10));
      },
      error: () => {},
    });
  }

  private score(f: RecentFinding): number {
    const sev = SEVERITY_WEIGHT[(f.severity || '').toUpperCase()] ?? 0.4;
    const norm = Math.min(1, (f.score ?? 0) / 100);
    return Math.round(sev * (0.5 + 0.5 * norm) * 100);
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
}
