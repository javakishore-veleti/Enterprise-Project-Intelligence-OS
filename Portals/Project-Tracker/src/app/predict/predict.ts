import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { map } from 'rxjs/operators';

import { EarlyWarning, Forecast, ForecastSummary, Scenario, ScenarioSummary } from '../models/analysis';
import { PortfolioProject, PortfolioSummary } from '../models/portfolio';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';
import { About } from '../ui/about';
import { UserScopeService } from '../ui/user-scope.service';

type Sub = 'forecasts' | 'scenarios' | 'warnings' | 'history';

/** A suggested what-if the agent can simulate in one click. */
interface ScenarioProbe { label: string; text: string; }

/**
 * Predict = the projection surface. It answers "what will happen next" and never
 * commits an action (that's Decide). Four views: the agent's ranked delivery
 * Forecasts (a call with a credible interval), the Digital-Twin Scenario simulator
 * (what-if + dependency cascade), proactive Early-Warnings, and persisted History.
 */
@Component({
  selector: 'app-predict',
  imports: [FormsModule, RouterLink, DecimalPipe, About],
  templateUrl: './predict.html',
  styleUrl: './predict.css',
})
export class Predict {
  private readonly projectsService = inject(ProjectsService);
  private readonly risk = inject(RiskAnalyticsService);
  protected readonly scope = inject(UserScopeService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly subview = toSignal(
    this.route.paramMap.pipe(
      map((p) => {
        const v = p.get('view');
        return v === 'scenarios' || v === 'warnings' || v === 'history' ? v : 'forecasts';
      }),
    ),
    { initialValue: 'forecasts' as Sub },
  );

  // project list (for the forecast queue + scenario picker)
  protected readonly summary = signal<PortfolioSummary | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly allProjects = computed<PortfolioProject[]>(() => this.summary()?.top_projects ?? []);

  /** Top-10 at-risk projects the agent will forecast (highest risk first). */
  protected readonly forecastQueue = computed<PortfolioProject[]>(() =>
    this.allProjects().filter((p) => p.risk_score != null).slice(0, 10),
  );

  // --- forecast state ---
  protected fcTarget = '';
  protected readonly forecasting = signal(false);
  protected readonly forecast = signal<Forecast | null>(null);
  protected readonly fcError = signal<string | null>(null);

  // --- scenario state ---
  protected scTarget = '';
  protected scText = '';
  protected readonly simulating = signal(false);
  protected readonly scenario = signal<Scenario | null>(null);
  protected readonly scError = signal<string | null>(null);
  protected readonly probes: ScenarioProbe[] = [
    { label: 'Add 2 engineers', text: 'add 2 engineers to clear the blocker backlog' },
    { label: 'Descope a feature', text: 'descope the lowest-priority feature to protect the release' },
    { label: 'Vendor slips 2 weeks', text: 'a key vendor dependency slips by 2 weeks' },
    { label: 'Freeze scope', text: 'freeze scope and stop taking new work for one sprint' },
  ];

  // --- early-warning state ---
  protected readonly warnings = signal<EarlyWarning[]>([]);
  protected readonly warningsLoading = signal(false);
  protected readonly warningsError = signal<string | null>(null);

  // --- history state ---
  protected histKind: 'forecasts' | 'scenarios' = 'forecasts';
  protected readonly fcHistory = signal<ForecastSummary[]>([]);
  protected readonly scHistory = signal<ScenarioSummary[]>([]);
  protected readonly histTotal = signal(0);
  protected readonly histLoading = signal(false);
  protected readonly histError = signal<string | null>(null);
  protected histQuery = '';
  protected readonly pageSize = 20;
  protected readonly maxRows = 100;
  protected offset = 0;

  constructor() {
    toObservable(this.scope.userKey).subscribe(() => {
      this.load();
      if (this.subview() === 'warnings') this.loadWarnings();
      if (this.subview() === 'history') this.reloadHistory();
    });
    toObservable(this.subview).subscribe((v) => {
      if (v === 'warnings') this.loadWarnings();
      if (v === 'history') this.reloadHistory();
    });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.projectsService.getPortfolioSummary(50, this.scope.userKey() || null).subscribe({
      next: (s) => {
        this.summary.set(s);
        this.loading.set(false);
        if (!this.scTarget) {
          const top = this.forecastQueue()[0];
          if (top) this.scTarget = top.project_key;
        }
      },
      error: () => { this.error.set('Unable to load projects. Is the Projects-API running on :8003?'); this.loading.set(false); },
    });
  }

  protected projectName(key: string): string {
    return this.allProjects().find((p) => p.project_key === key)?.name || key;
  }

  // --- forecasts ---
  protected runForecast(projectKey: string): void {
    if (!projectKey || this.forecasting()) return;
    this.fcTarget = projectKey;
    this.forecasting.set(true);
    this.fcError.set(null);
    this.forecast.set(null);
    this.risk.runForecast(projectKey, this.scope.userKey() || 'director').subscribe({
      next: (f) => { this.forecast.set(f); this.forecasting.set(false); },
      error: () => { this.fcError.set('The Forecast Agent could not run. Is RiskAnalytics-API on :8004 up (ANTHROPIC_API_KEY set)?'); this.forecasting.set(false); },
    });
  }
  protected resetForecast(): void { this.forecast.set(null); this.fcError.set(null); }

  // --- scenarios ---
  protected runScenario(): void {
    const key = this.scTarget;
    const text = this.scText.trim();
    if (!key || !text || this.simulating()) return;
    this.simulating.set(true);
    this.scError.set(null);
    this.scenario.set(null);
    this.risk.runScenario(key, text, this.scope.userKey() || 'director').subscribe({
      next: (s) => { this.scenario.set(s); this.simulating.set(false); },
      error: () => { this.scError.set('The Scenario Simulator could not run. Is RiskAnalytics-API on :8004 up (ANTHROPIC_API_KEY set)?'); this.simulating.set(false); },
    });
  }
  protected runProbe(p: ScenarioProbe): void { this.scText = p.text; this.runScenario(); }
  protected resetScenario(): void { this.scenario.set(null); this.scError.set(null); this.scText = ''; }

  // --- early-warnings ---
  private loadWarnings(): void {
    this.warningsLoading.set(true);
    this.warningsError.set(null);
    this.risk.getEarlyWarnings(this.scope.userKey() || null, 15).subscribe({
      next: (r) => { this.warnings.set(r.items); this.warningsLoading.set(false); },
      error: () => { this.warningsError.set('Unable to load early-warnings. Is RiskAnalytics-API on :8004 up?'); this.warningsLoading.set(false); },
    });
  }

  // --- history ---
  protected setHistKind(k: 'forecasts' | 'scenarios'): void { this.histKind = k; this.reloadHistory(); }
  private reloadHistory(): void { this.offset = 0; this.loadHistory(); }
  protected loadHistory(): void {
    this.histLoading.set(true);
    this.histError.set(null);
    const opts = { scope: this.scope.userKey() || null, q: this.histQuery, limit: this.pageSize, offset: this.offset };
    if (this.histKind === 'forecasts') {
      this.risk.listForecasts(opts).subscribe({
        next: (page) => { this.fcHistory.set(page.items); this.histTotal.set(Math.min(page.total, this.maxRows)); this.histLoading.set(false); },
        error: () => { this.histError.set('Unable to load forecast history.'); this.histLoading.set(false); },
      });
    } else {
      this.risk.listScenarios(opts).subscribe({
        next: (page) => { this.scHistory.set(page.items); this.histTotal.set(Math.min(page.total, this.maxRows)); this.histLoading.set(false); },
        error: () => { this.histError.set('Unable to load scenario history.'); this.histLoading.set(false); },
      });
    }
  }
  protected searchHistory(): void { this.reloadHistory(); }
  protected nextPage(): void { if (this.offset + this.pageSize < this.histTotal()) { this.offset += this.pageSize; this.loadHistory(); } }
  protected prevPage(): void { if (this.offset > 0) { this.offset = Math.max(0, this.offset - this.pageSize); this.loadHistory(); } }
  protected get pageStart(): number { return this.histTotal() === 0 ? 0 : this.offset + 1; }
  protected get pageEnd(): number { return Math.min(this.offset + this.pageSize, this.histTotal()); }
  protected get canPrev(): boolean { return this.offset > 0; }
  protected get canNext(): boolean { return this.offset + this.pageSize < this.histTotal(); }

  protected openForecast(id: string): void {
    this.router.navigate(['/predict/forecasts']);
    this.forecasting.set(true); this.fcError.set(null); this.forecast.set(null);
    this.risk.getForecast(id).subscribe({
      next: (f) => { this.forecast.set(f); this.fcTarget = f.project_key; this.forecasting.set(false); },
      error: () => { this.fcError.set('Unable to load that forecast.'); this.forecasting.set(false); },
    });
  }
  protected openScenario(id: string): void {
    this.router.navigate(['/predict/scenarios']);
    this.simulating.set(true); this.scError.set(null); this.scenario.set(null);
    this.risk.getScenario(id).subscribe({
      next: (s) => { this.scenario.set(s); this.scTarget = s.project_key; this.simulating.set(false); },
      error: () => { this.scError.set('Unable to load that scenario.'); this.simulating.set(false); },
    });
  }

  // --- formatting ---
  protected pct(v: number | null | undefined): number { return Math.round((v ?? 0) * 100); }
  protected signedPct(v: number | null | undefined): string { const n = Math.round((v ?? 0) * 100); return (n > 0 ? '+' : '') + n + '%'; }
  protected outlookClass(o: string | null | undefined): string {
    return o === 'off_track' ? 'high' : o === 'at_risk' ? 'medium' : 'low';
  }
  protected probClass(p: number): string { return p >= 66 ? 'low' : p >= 40 ? 'medium' : 'high'; }
  protected sevClass(s: string): string { return (s || 'low').toLowerCase(); }
  protected magClass(m: string): string { return (m || 'low').toLowerCase(); }
  protected riskScoreClass(score: number): string { return score >= 66 ? 'high' : score >= 33 ? 'medium' : 'low'; }
}
