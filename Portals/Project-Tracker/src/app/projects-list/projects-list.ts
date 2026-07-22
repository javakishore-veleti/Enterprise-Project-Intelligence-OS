import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { Investigation } from '../models/analysis';
import { PortfolioProject, PortfolioSummary } from '../models/portfolio';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';
import { About } from '../ui/about';
import { UserScopeService } from '../ui/user-scope.service';

/** A suggested investigation prompt the user can fire in one click. */
interface Probe {
  label: string;
  question: string;
}

/**
 * Investigate = the autonomous Investigation Agent surface. You point the agent at
 * a project (and optionally ask it something), and it forms hypotheses, calls
 * evidence-store tools, reasons, and concludes with a root cause + confidence +
 * an evidence trail you can inspect and argue with. The raw evidence register is
 * the substrate below — the human's verification surface, never the hero.
 */
@Component({
  selector: 'app-projects-list',
  imports: [FormsModule, RouterLink, DecimalPipe, About],
  templateUrl: './projects-list.html',
  styleUrl: './projects-list.css',
})
export class ProjectsList {
  private readonly projectsService = inject(ProjectsService);
  private readonly risk = inject(RiskAnalyticsService);
  protected readonly scope = inject(UserScopeService);

  // --- evidence substrate (the register the agent reasons over) ---
  protected readonly summary = signal<PortfolioSummary | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected view: 'cards' | 'table' = 'cards';
  protected query = '';
  protected showEvidence = signal(false);

  // --- the Investigation Agent ---
  protected target = '';
  protected question = '';
  protected readonly investigating = signal(false);
  protected readonly investigation = signal<Investigation | null>(null);
  protected readonly invError = signal<string | null>(null);

  protected readonly probes: Probe[] = [
    { label: 'Why is delivery at risk?', question: 'Why is delivery at risk on this project?' },
    { label: 'Top root cause', question: 'What is the single biggest root cause of risk here?' },
    { label: 'Bus-factor / ownership', question: 'Is there a bus-factor or contributor-concentration problem?' },
    { label: 'Blocked by dependencies?', question: 'Is this project being held up by blocking dependencies?' },
    { label: 'Quality / reopen churn', question: 'Is reopen churn or defect quality dragging this project?' },
  ];

  protected readonly allProjects = computed<PortfolioProject[]>(() => this.summary()?.top_projects ?? []);

  /** Projects in scope, filtered by the search query (evidence browser). */
  protected readonly projects = computed<PortfolioProject[]>(() => {
    const all = this.allProjects();
    const q = this.query.trim().toLowerCase();
    return q ? all.filter((p) => p.project_key.toLowerCase().includes(q) || (p.name || '').toLowerCase().includes(q)) : all;
  });
  protected readonly totals = computed(() => this.summary()?.totals ?? { projects: 0, issues: 0, open_issues: 0 });
  protected readonly bands = computed(() => this.summary()?.risk_bands ?? { high: 0, medium: 0, low: 0, unscored: 0 });

  /** Confidence as a whole-percent for the gauge. */
  protected readonly confidencePct = computed(() => Math.round((this.investigation()?.confidence ?? 0) * 100));

  constructor() {
    toObservable(this.scope.userKey).subscribe(() => this.load());
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.projectsService.getPortfolioSummary(50, this.scope.userKey() || null).subscribe({
      next: (s) => {
        this.summary.set(s);
        this.loading.set(false);
        // Default the investigator to the highest-risk project in scope.
        if (!this.target) {
          const top = (s.top_projects ?? []).find((p) => p.risk_score != null);
          if (top) this.target = top.project_key;
        }
      },
      error: () => { this.error.set('Unable to load projects. Is the Projects-API running on :8003?'); this.loading.set(false); },
    });
  }

  // --- Investigation Agent actions ---

  protected investigate(): void {
    const key = this.target;
    if (!key || this.investigating()) return;
    this.investigating.set(true);
    this.invError.set(null);
    this.risk.investigate(key, this.question, this.scope.userKey() || 'director').subscribe({
      next: (inv) => { this.investigation.set(inv); this.investigating.set(false); },
      error: () => {
        this.invError.set('The Investigation Agent could not run. Is the RiskAnalytics-API on :8004 up (with ANTHROPIC_API_KEY set)?');
        this.investigating.set(false);
      },
    });
  }

  /** Fire a suggested probe against the current target. */
  protected runProbe(p: Probe): void {
    this.question = p.question;
    this.investigate();
  }

  /** Steer: ask a follow-up on the same target (re-investigate). */
  protected steer(): void { this.investigate(); }

  protected reset(): void { this.investigation.set(null); this.invError.set(null); this.question = ''; }

  protected projectName(key: string): string {
    return this.allProjects().find((p) => p.project_key === key)?.name || key;
  }

  // --- shared formatting ---
  protected bandClass(band: string): string { return (band || 'low').toLowerCase(); }
  protected scoreClass(score: number): string { return score >= 66 ? 'high' : score >= 33 ? 'medium' : 'low'; }
  protected confClass(pct: number): string { return pct >= 66 ? 'high' : pct >= 40 ? 'medium' : 'low'; }
  protected pctOf(v: number): number { return Math.round((v ?? 0) * 100); }
}
