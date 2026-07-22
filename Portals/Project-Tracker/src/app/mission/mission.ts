import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { AttentionItem } from '../models/analysis';
import { PortfolioSummary } from '../models/portfolio';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';
import { About } from '../ui/about';
import { UserScopeService } from '../ui/user-scope.service';

@Component({
  selector: 'app-mission',
  imports: [RouterLink, DecimalPipe, About],
  templateUrl: './mission.html',
  styleUrl: './mission.css',
})
export class Mission {
  private readonly projectsService = inject(ProjectsService);
  private readonly riskService = inject(RiskAnalyticsService);
  protected readonly scope = inject(UserScopeService);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly summary = signal<PortfolioSummary | null>(null);
  protected readonly attention = signal<AttentionItem[]>([]);
  protected readonly attentionTotal = signal(0);

  protected readonly topProjects = computed(() => (this.summary()?.top_projects ?? []).slice(0, 5));
  protected readonly greeting = computed(() => {
    const h = new Date().getHours();
    return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  });

  constructor() {
    // Reload whenever the global scope (masthead switcher / SSO identity) changes.
    toObservable(this.scope.userKey).subscribe(() => this.load());
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.attention.set([]);
    this.attentionTotal.set(0);

    this.projectsService.getPortfolioSummary(15, this.scope.userKey() || null).subscribe({
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

  /** Ranked attention feed (server-side), scoped to the current user. Top 5 = focus. */
  private loadAttention(s: PortfolioSummary): void {
    const projects = s.scope?.scoped ? s.top_projects.map((p) => p.project_key) : undefined;
    this.riskService.getAttention(5, { projects }).subscribe({
      next: (r) => { this.attentionTotal.set(r.total); this.attention.set(r.items); },
      error: () => {},
    });
  }

  protected primaryAction(a: AttentionItem): string | null { return a.recommended_actions?.[0] ?? null; }
  protected pctOf(v: number): number { return Math.round((v ?? 0) * 100); }
  protected bandClass(band: string): string { return (band || 'low').toLowerCase(); }
  protected severityClass(sev: string): string { return (sev || 'unknown').toLowerCase(); }
  protected scoreClass(score: number): string { return score >= 66 ? 'high' : score >= 33 ? 'medium' : 'low'; }
}
