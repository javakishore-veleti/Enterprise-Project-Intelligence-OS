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

  // --- evidence substrate (the register the agent reasons over) ---
  protected readonly summary = signal<PortfolioSummary | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected view: 'cards' | 'table' = 'cards';
  protected query = '';
  protected showEvidence = signal(false);

  // --- the Investigation Agent ---
  /** The active investigation target (set by the agent's queue, not typed by the user). */
  protected target = '';
  /** Free-text follow-up for the *advanced* steer/ask affordance only. */
  protected question = '';
  protected readonly investigating = signal(false);
  protected readonly investigation = signal<Investigation | null>(null);
  protected readonly invError = signal<string | null>(null);
  protected readonly activeQuestion = signal<string>('');
  protected showAdvanced = signal(false);

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
    toObservable(this.scope.userKey).subscribe(() => this.load());
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
