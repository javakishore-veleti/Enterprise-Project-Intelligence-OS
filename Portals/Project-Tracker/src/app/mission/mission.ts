import { DecimalPipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AttentionItem } from '../models/analysis';
import { PortfolioSummary } from '../models/portfolio';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';

/** Demo identities (seam for real SSO). Keys match the seeded project_assignments. */
const USERS: ReadonlyArray<{ key: string; label: string }> = [
  { key: '', label: 'Director — all projects' },
  { key: 'mgr-apac', label: 'APAC Delivery Manager' },
  { key: 'mgr-data', label: 'Data Platform Manager' },
];

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

  // Focus: show only the top 5 riskiest on the home; "View all" for the rest.
  protected readonly topProjects = computed(() => (this.summary()?.top_projects ?? []).slice(0, 5));
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
   * Ranked attention feed from the server (/analysis/attention), scoped to the
   * user's projects. The product's value is FOCUS — surface only the top 5.
   */
  private loadAttention(s: PortfolioSummary): void {
    const projects = s.scope?.scoped ? s.top_projects.map((p) => p.project_key) : undefined;
    this.riskService.getAttention(5, { projects }).subscribe({
      next: (r) => {
        this.attentionTotal.set(r.total);
        this.attention.set(r.items);
      },
      error: () => {},
    });
  }

  /** First recommended action — the single "what to do now". */
  protected primaryAction(a: AttentionItem): string | null {
    return a.recommended_actions?.[0] ?? null;
  }
  protected pctOf(v: number): number {
    return Math.round((v ?? 0) * 100);
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
