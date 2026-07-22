import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { map } from 'rxjs/operators';

import { Investigation, InvestigationSummary } from '../models/analysis';
import { PortfolioProject, PortfolioSummary } from '../models/portfolio';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';
import { About } from '../ui/about';
import { UserScopeService } from '../ui/user-scope.service';

/** An investigation the AGENT scoped on its own — target + the question it chose, and why. */
interface QueuedInvestigation {
  project: PortfolioProject;
  question: string;
  angle: string;   // short label of the investigation angle the agent picked
  reason: string;  // why the agent flagged this (the triggering signal)
  signal: 'high' | 'medium' | 'low';
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
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  /** Sub-view driven by the sidebar sub-nav (?v=ask|history|evidence). */
  protected readonly subview = toSignal(
    this.route.queryParamMap.pipe(
      map((p) => {
        const v = p.get('v');
        return v === 'ask' || v === 'history' || v === 'evidence' ? v : 'new';
      }),
    ),
    { initialValue: 'new' as 'new' | 'ask' | 'history' | 'evidence' },
  );

  // --- Investigations history (persisted) ---
  protected readonly history = signal<InvestigationSummary[]>([]);
  protected readonly historyTotal = signal(0);
  protected readonly historyLoading = signal(false);
  protected readonly historyError = signal<string | null>(null);
  protected readonly pageSize = 20;
  protected readonly maxRows = 100; // show at most the newest 100
  protected offset = 0;
  protected historyQuery = '';

  // --- evidence substrate (the register the agent reasons over) ---
  protected readonly summary = signal<PortfolioSummary | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected view: 'cards' | 'table' = 'cards';
  protected query = '';

  // --- the Investigation Agent ---
  /** The active investigation target (set by the agent's queue, not typed by the user). */
  protected target = '';
  /** Free-text follow-up for the *advanced* steer/ask affordance only. */
  protected question = '';
  protected readonly investigating = signal(false);
  protected readonly investigation = signal<Investigation | null>(null);
  protected readonly invError = signal<string | null>(null);
  protected readonly activeQuestion = signal<string>('');

  protected readonly allProjects = computed<PortfolioProject[]>(() => this.summary()?.top_projects ?? []);

  /**
   * The agent's own investigation queue: it picks WHAT to investigate (highest-risk
   * projects in scope) and WHICH question to ask (derived from each project's dominant
   * evidence signal) — so the human never has to know the right question. Top-6.
   */
  protected readonly queue = computed<QueuedInvestigation[]>(() =>
    this.allProjects()
      .filter((p) => p.risk_score != null)
      .slice(0, 10)
      .map((p) => this.scopeInvestigation(p)),
  );

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
    toObservable(this.scope.userKey).subscribe(() => { this.load(); if (this.subview() === 'history') this.reloadHistory(); });
    toObservable(this.subview).subscribe((v) => { if (v === 'history') this.reloadHistory(); });
  }

  // --- Investigations history ---

  private reloadHistory(): void { this.offset = 0; this.loadHistory(); }

  protected loadHistory(): void {
    this.historyLoading.set(true);
    this.historyError.set(null);
    this.risk.listInvestigations({
      scope: this.scope.userKey() || null,
      q: this.historyQuery,
      limit: this.pageSize,
      offset: this.offset,
    }).subscribe({
      next: (page) => {
        this.history.set(page.items);
        this.historyTotal.set(Math.min(page.total, this.maxRows));
        this.historyLoading.set(false);
      },
      error: () => {
        this.historyError.set('Unable to load investigation history. Is the RiskAnalytics-API on :8004 up?');
        this.historyLoading.set(false);
      },
    });
  }

  protected searchHistory(): void { this.reloadHistory(); }

  protected nextPage(): void {
    if (this.offset + this.pageSize < this.historyTotal()) { this.offset += this.pageSize; this.loadHistory(); }
  }
  protected prevPage(): void {
    if (this.offset > 0) { this.offset = Math.max(0, this.offset - this.pageSize); this.loadHistory(); }
  }
  protected get pageStart(): number { return this.historyTotal() === 0 ? 0 : this.offset + 1; }
  protected get pageEnd(): number { return Math.min(this.offset + this.pageSize, this.historyTotal()); }
  protected get canPrev(): boolean { return this.offset > 0; }
  protected get canNext(): boolean { return this.offset + this.pageSize < this.historyTotal(); }

  /** Open a persisted investigation into the briefing (switches to the New view). */
  protected openInvestigation(id: string): void {
    this.investigating.set(true);
    this.invError.set(null);
    this.router.navigate([], { queryParams: { v: null }, queryParamsHandling: 'merge' });
    this.risk.getInvestigation(id).subscribe({
      next: (inv) => { this.investigation.set(inv); this.target = inv.project_key; this.investigating.set(false); },
      error: () => { this.invError.set('Unable to load that investigation.'); this.investigating.set(false); },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.projectsService.getPortfolioSummary(50, this.scope.userKey() || null).subscribe({
      next: (s) => {
        this.summary.set(s);
        this.loading.set(false);
      },
      error: () => { this.error.set('Unable to load projects. Is the Projects-API running on :8003?'); this.loading.set(false); },
    });
  }

  /**
   * The agent decides what to ask about a project from its dominant evidence signal —
   * so the user never has to formulate the right question.
   */
  private scopeInvestigation(p: PortfolioProject): QueuedInvestigation {
    const reopen = p.reopen_rate ?? 0;
    const blockers = p.blocker_count ?? 0;
    const aging = p.issue_aging_days ?? 0;
    const signal: 'high' | 'medium' | 'low' = p.risk_score >= 66 ? 'high' : p.risk_score >= 33 ? 'medium' : 'low';
    if (reopen >= 0.25) {
      return { project: p, signal, angle: 'Quality / reopen churn',
        reason: `${Math.round(reopen * 100)}% reopen rate`,
        question: 'Is reopen churn or defect quality dragging delivery, and where is it concentrated?' };
    }
    if (blockers > 50) {
      return { project: p, signal, angle: 'Blocking dependencies',
        reason: `${blockers.toLocaleString()} blockers`,
        question: 'Is this project being held up by blocking dependencies, and which ones?' };
    }
    if (aging > 60) {
      return { project: p, signal, angle: 'Aging / stalled work',
        reason: `${Math.round(aging)}d avg age`,
        question: 'Why are issues aging without resolution, and is the backlog stalling?' };
    }
    return { project: p, signal, angle: 'Root-cause of risk',
      reason: `risk ${Math.round(p.risk_score)}`,
      question: 'What is the single biggest root cause of delivery risk on this project?' };
  }

  // --- Investigation Agent actions ---

  /** Run the agent against a target with the question the agent (or user) chose. */
  private run(projectKey: string, question: string): void {
    if (!projectKey || this.investigating()) return;
    this.target = projectKey;
    this.activeQuestion.set(question);
    this.investigating.set(true);
    this.invError.set(null);
    this.investigation.set(null);
    this.risk.investigate(projectKey, question, this.scope.userKey() || 'director').subscribe({
      next: (inv) => { this.investigation.set(inv); this.investigating.set(false); },
      error: () => {
        this.invError.set('The Investigation Agent could not run. Is the RiskAnalytics-API on :8004 up (with ANTHROPIC_API_KEY set)?');
        this.investigating.set(false);
      },
    });
  }

  /** Run a queued (agent-scoped) investigation — one click, no typing. */
  protected runQueued(q: QueuedInvestigation): void { this.run(q.project.project_key, q.question); }

  /** Advanced: run whatever the user typed (power users only). */
  protected runManual(): void {
    if (this.target) this.run(this.target, this.question);
  }

  /** Steer: re-investigate the same target with a follow-up. */
  protected steer(): void { if (this.target) this.run(this.target, this.question); }

  protected reset(): void { this.investigation.set(null); this.invError.set(null); this.question = ''; }

  /** Investigate a project chosen from the evidence substrate (agent picks the angle). */
  protected investigateProject(p: PortfolioProject): void { this.runQueued(this.scopeInvestigation(p)); }

  protected projectName(key: string): string {
    return this.allProjects().find((p) => p.project_key === key)?.name || key;
  }

  // --- shared formatting ---
  protected bandClass(band: string): string { return (band || 'low').toLowerCase(); }
  protected scoreClass(score: number): string { return score >= 66 ? 'high' : score >= 33 ? 'medium' : 'low'; }
  protected confClass(pct: number): string { return pct >= 66 ? 'high' : pct >= 40 ? 'medium' : 'low'; }
  protected pctOf(v: number): number { return Math.round((v ?? 0) * 100); }
}
