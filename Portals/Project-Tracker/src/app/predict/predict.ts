import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, map } from 'rxjs/operators';

import { EarlyWarning, Forecast, ForecastSummary, Scenario, ScenarioSummary } from '../models/analysis';
import { ProjectGroup } from '../models/group';
import { ForecastSubjectFacet, ForecastSubjectsResponse, PortfolioProject, PortfolioSummary, ProjectSearchItem } from '../models/portfolio';
import { GroupsService } from '../services/groups.service';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';
import { About } from '../ui/about';
import { UserScopeService } from '../ui/user-scope.service';

type Sub = 'forecasts' | 'scenarios' | 'warnings' | 'history';

/** Forecast sub-scope: the whole project, or one release/component/tag within it. */
type FcScope = 'project' | 'release' | 'component' | 'tag';

/** A suggested what-if the agent can simulate in one click. */
interface ScenarioProbe { label: string; text: string; }

/**
 * The thing a Predict view is scoped to. `anchor` is the single project the
 * agent actually runs against — its own key for a project, or the highest-risk
 * member for a group (a group's cascade already surfaces the coupled projects).
 */
interface PredictTarget {
  type: 'project' | 'group';
  key: string;
  name: string;
  projectKeys: string[];
  anchor: string;
}

/** A project-group card with its rolled-up risk (max/avg member risk + anchor). */
interface GroupCard {
  group: ProjectGroup;
  max: number;
  avg: number;
  anchor: string;
  members: number;
}

/** A/B comparison of two forecast instances of the same subject (older → newer). */
interface ForecastDelta {
  a: ForecastSummary;
  b: ForecastSummary;
  onTimeA: number;
  onTimeB: number;
  onTimeDelta: number;
  confA: number;
  confB: number;
  confDelta: number;
  outlookChanged: boolean;
  outlookImproved: boolean | null;
}

/**
 * Predict = the projection surface. It answers "what will happen next" and never
 * commits an action (that's Decide). Four views: the agent's ranked delivery
 * Forecasts (a call with a credible interval), the Digital-Twin Scenario simulator
 * (what-if + dependency cascade), proactive Early-Warnings, and persisted History.
 */
@Component({
  selector: 'app-predict',
  imports: [FormsModule, RouterLink, DecimalPipe, NgTemplateOutlet, About],
  templateUrl: './predict.html',
  styleUrl: './predict.css',
})
export class Predict {
  private readonly projectsService = inject(ProjectsService);
  private readonly groupsService = inject(GroupsService);
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

  // project list (for the forecast queue + target selector)
  protected readonly summary = signal<PortfolioSummary | null>(null);
  protected readonly groups = signal<ProjectGroup[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly allProjects = computed<PortfolioProject[]>(() => this.summary()?.top_projects ?? []);

  /** Top-10 at-risk projects the agent will forecast (highest risk first). */
  protected readonly forecastQueue = computed<PortfolioProject[]>(() =>
    this.allProjects().filter((p) => p.risk_score != null).slice(0, 10),
  );

  /** Project-group cards with rolled-up (max/avg) member risk + highest-risk anchor. */
  protected readonly groupCards = computed<GroupCard[]>(() =>
    this.groups().map((g) => ({ group: g, ...this.groupRisk(g) })),
  );

  // ---- target selection (shared by Scenarios + Early-Warning) ----
  /** The project/group the Scenarios what-if panel is scoped to (null → show selector). */
  protected readonly scTargetSel = signal<PredictTarget | null>(null);
  /** The project/group Early-Warning is watching (null → show selector). */
  protected readonly warnTarget = signal<PredictTarget | null>(null);

  // ---- server-backed project search (shared selector) ----
  /** Search box text; empty → the selector shows the summary's top projects (default). */
  protected readonly projQuery = signal('');
  /** Accumulated search-result cards (grows via Load more). */
  protected readonly searchResults = signal<ProjectSearchItem[]>([]);
  protected readonly searchTotal = signal(0);
  protected readonly searchLoading = signal(false);
  protected readonly searchLoadingMore = signal(false);
  protected readonly searchError = signal<string | null>(null);
  /** Offset of the next page to fetch (= count already loaded). */
  private searchOffset = 0;
  private readonly searchPageSize = 24;
  /** True while a non-empty query is driving the selector (server results shown). */
  protected readonly searchActive = computed(() => this.projQuery().trim().length > 0);
  /** More server rows exist beyond what's loaded. */
  protected readonly canLoadMoreProjects = computed(() => this.searchResults().length < this.searchTotal());

  // ---- KPI tiles for the Early-Warning mini-dashboard ----
  protected readonly kpiProjects = computed(() => this.allProjects().length);
  protected readonly kpiAtRisk = computed(
    () => this.allProjects().filter((p) => p.risk_band === 'High' || p.risk_band === 'Medium').length,
  );
  protected readonly kpiGroups = computed(() => this.groups().length);
  protected readonly kpiHighWarnings = computed(
    () => this.warnings().filter((w) => this.sevClass(w.severity) === 'high').length,
  );

  // --- forecast state ---
  protected fcTarget = '';
  protected readonly forecasting = signal(false);
  protected readonly forecast = signal<Forecast | null>(null);
  protected readonly fcError = signal<string | null>(null);
  /** The project/group whose forecasts we're tracking (null → show subject selector). */
  protected readonly fcSubject = signal<PredictTarget | null>(null);
  /** Past forecast runs for the selected subject (its projects' rows), newest first. */
  protected readonly fcInstances = signal<ForecastSummary[]>([]);
  protected readonly fcInstancesLoading = signal(false);
  protected readonly fcInstancesError = signal<string | null>(null);
  /** The forecast_id currently shown in the briefing (highlights its instance row). */
  protected readonly activeForecastId = signal<string | null>(null);
  /** forecast_ids selected for A/B compare (max 2). */
  protected readonly fcCompare = signal<ReadonlySet<string>>(new Set());

  // --- forecast sub-scope (release / component / tag within a project) ---
  /** Which sub-scope the next forecast runs against; 'project' = whole project (default). */
  protected readonly fcScope = signal<FcScope>('project');
  /** The chosen facet value (release/component/tag) when fcScope !== 'project'. */
  protected readonly fcScopeValue = signal<string | null>(null);
  /** Filter text over the (up-to-50) facet values, kept as a signal so the list reacts. */
  protected readonly fcFacetFilter = signal('');
  /** Facets for the current project (releases/components/tags + counts); null until loaded. */
  protected readonly fcSubjects = signal<ForecastSubjectsResponse | null>(null);
  protected readonly fcSubjectsLoading = signal(false);
  protected readonly fcSubjectsError = signal<string | null>(null);
  /** Per-project facet cache so re-picking a scope doesn't re-fetch. */
  private readonly subjectsCache = new Map<string, ForecastSubjectsResponse>();
  /** Cap on rendered facet rows so a 50-value project stays usable (filter to narrow). */
  protected readonly maxFacetRows = 60;

  /** The facet list for the active sub-scope (empty for 'project'). */
  protected readonly activeFacets = computed<ForecastSubjectFacet[]>(() => {
    const subj = this.fcSubjects();
    const scope = this.fcScope();
    if (!subj || scope === 'project') return [];
    return scope === 'release' ? subj.releases : scope === 'component' ? subj.components : subj.tags;
  });
  /** Total facet values available for the active sub-scope. */
  protected readonly facetTotal = computed<number>(() => this.activeFacets().length);
  /** Filtered + capped facet rows actually rendered. */
  protected readonly filteredFacets = computed<ForecastSubjectFacet[]>(() => {
    const q = this.fcFacetFilter().trim().toLowerCase();
    const list = q ? this.activeFacets().filter((f) => f.value.toLowerCase().includes(q)) : this.activeFacets();
    return list.slice(0, this.maxFacetRows);
  });
  /** Issue count for the currently-chosen facet value (for the scope header). */
  protected readonly fcScopeCount = computed<number | null>(() => {
    const v = this.fcScopeValue();
    if (!v) return null;
    return this.activeFacets().find((f) => f.value === v)?.count ?? null;
  });
  /** True when a sub-scope is picked but no value chosen yet (blocks "Run new forecast"). */
  protected readonly fcNeedsScopeValue = computed<boolean>(() => this.fcScope() !== 'project' && !this.fcScopeValue());

  /** Rolled-up risk score of the selected forecast subject (project score or group max). */
  protected readonly fcSubjectRisk = computed<number | null>(() => {
    const t = this.fcSubject();
    if (!t) return null;
    if (t.type === 'project') return this.projectByKey(t.key)?.risk_score ?? null;
    const g = this.groups().find((x) => x.group_key === t.key);
    return g ? this.groupRisk(g).max : null;
  });

  // --- scenario state ---
  protected scText = '';
  protected newProbe = '';
  protected readonly simulating = signal(false);
  protected readonly scenario = signal<Scenario | null>(null);
  protected readonly scError = signal<string | null>(null);
  /** The target a rendered scenario was simulated on (for group cascade labelling). */
  protected readonly scResultTarget = signal<PredictTarget | null>(null);
  /** Built-in what-if probes (always offered). */
  protected readonly defaultProbes: ScenarioProbe[] = [
    { label: 'Add 2 engineers', text: 'add 2 engineers to clear the blocker backlog' },
    { label: 'Descope a feature', text: 'descope the lowest-priority feature to protect the release' },
    { label: 'Vendor slips 2 weeks', text: 'a key vendor dependency slips by 2 weeks' },
    { label: 'Freeze scope', text: 'freeze scope and stop taking new work for one sprint' },
  ];
  private static readonly PROBES_KEY = 'predict.customProbes.v1';
  /** User-added what-if probes, persisted in localStorage so they survive reloads. */
  protected readonly customProbes = signal<ScenarioProbe[]>(this.loadCustomProbes());

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

  /** Selected history criteria as prefixed ids: `p:<projectKey>` / `g:<groupKey>`. */
  protected readonly histSel = signal<ReadonlySet<string>>(new Set());

  constructor() {
    this.loadGroups();
    toObservable(this.scope.userKey).subscribe(() => {
      this.load();
      if (this.searchActive()) this.runProjectSearch(this.projQuery().trim());
      if (this.subview() === 'warnings' && this.warnTarget()) this.loadWarnings();
      if (this.subview() === 'forecasts' && this.fcSubject()) this.loadForecastInstances();
      if (this.subview() === 'history') this.reloadHistory();
    });
    toObservable(this.subview).subscribe((v) => {
      if (v === 'history') this.reloadHistory();
    });
    // Debounced server-backed project search for the shared card selector.
    toObservable(this.projQuery)
      .pipe(debounceTime(300))
      .subscribe((q) => this.runProjectSearch(q.trim()));
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.projectsService.getPortfolioSummary(50, this.scope.userKey() || null).subscribe({
      next: (s) => { this.summary.set(s); this.loading.set(false); },
      error: () => { this.error.set('Unable to load projects. Is the Projects-API running on :8003?'); this.loading.set(false); },
    });
  }

  private loadGroups(): void {
    this.groupsService.list().subscribe({
      next: (r) => this.groups.set(r.items),
      error: () => this.groups.set([]),
    });
  }

  protected projectName(key: string): string {
    return this.allProjects().find((p) => p.project_key === key)?.name || key;
  }

  // ---- target selector (shared) ----
  private projectByKey(key: string): PortfolioProject | undefined {
    return this.allProjects().find((p) => p.project_key === key);
  }

  /** Rolled-up risk for a group: max + avg member risk, and the highest-risk member as anchor. */
  protected groupRisk(g: ProjectGroup): { max: number; avg: number; anchor: string; members: number } {
    const members = g.project_keys
      .map((k) => this.projectByKey(k))
      .filter((p): p is PortfolioProject => !!p);
    if (!members.length) return { max: 0, avg: 0, anchor: g.project_keys[0] ?? g.group_key, members: 0 };
    let max = -1, sum = 0, anchor = members[0].project_key;
    for (const m of members) {
      const s = m.risk_score ?? 0;
      sum += s;
      if (s > max) { max = s; anchor = m.project_key; }
    }
    return { max: Math.round(max), avg: Math.round(sum / members.length), anchor, members: members.length };
  }

  private targetFromProject(p: PortfolioProject): PredictTarget {
    return { type: 'project', key: p.project_key, name: p.name || p.project_key, projectKeys: [p.project_key], anchor: p.project_key };
  }
  private targetFromProjectKey(key: string): PredictTarget {
    const p = this.projectByKey(key);
    return p ? this.targetFromProject(p) : { type: 'project', key, name: key, projectKeys: [key], anchor: key };
  }

  // ---- server-backed project search ----
  /** Run a fresh scoped search (offset 0). Empty query clears back to the default. */
  private runProjectSearch(q: string): void {
    if (!q) {
      this.searchResults.set([]);
      this.searchTotal.set(0);
      this.searchOffset = 0;
      this.searchError.set(null);
      this.searchLoading.set(false);
      return;
    }
    this.searchOffset = 0;
    this.searchLoading.set(true);
    this.searchError.set(null);
    this.projectsService
      .searchScopedProjects({ scope: this.scope.userKey() || null, q, limit: this.searchPageSize, offset: 0 })
      .subscribe({
        next: (r) => { this.searchResults.set(r.items); this.searchTotal.set(r.total); this.searchOffset = r.items.length; this.searchLoading.set(false); },
        error: () => { this.searchError.set('Unable to search projects. Is the Projects-API running on :8003?'); this.searchLoading.set(false); },
      });
  }

  /** Fetch the next page of search results and append (Load more). */
  protected loadMoreProjects(): void {
    const q = this.projQuery().trim();
    if (!q || this.searchLoadingMore()) return;
    this.searchLoadingMore.set(true);
    this.searchError.set(null);
    this.projectsService
      .searchScopedProjects({ scope: this.scope.userKey() || null, q, limit: this.searchPageSize, offset: this.searchOffset })
      .subscribe({
        next: (r) => { this.searchResults.update((rows) => [...rows, ...r.items]); this.searchTotal.set(r.total); this.searchOffset += r.items.length; this.searchLoadingMore.set(false); },
        error: () => { this.searchError.set('Unable to load more projects.'); this.searchLoadingMore.set(false); },
      });
  }

  protected clearProjectSearch(): void { this.projQuery.set(''); }

  private targetFromSearchItem(it: ProjectSearchItem): PredictTarget {
    return { type: 'project', key: it.project_key, name: it.name || it.project_key, projectKeys: [it.project_key], anchor: it.project_key };
  }
  /** Pick a searched project card — selects exactly like a summary card. */
  protected pickSearchItem(it: ProjectSearchItem): void { this.chooseTarget(this.targetFromSearchItem(it)); }
  /** Risk band CSS class for a search item (null risk_score → 'none'). */
  protected searchRiskClass(score: number | null): string {
    return score == null ? 'none' : this.riskScoreClass(score);
  }

  /** Pick a project card in the shared selector — routes to the active view's target. */
  protected pickProject(p: PortfolioProject): void { this.chooseTarget(this.targetFromProject(p)); }
  /** Pick a group card in the shared selector — routes to the active view's target. */
  protected pickGroup(gc: GroupCard): void {
    this.chooseTarget({ type: 'group', key: gc.group.group_key, name: gc.group.name, projectKeys: [...gc.group.project_keys], anchor: gc.anchor });
  }
  /** Early-Warning "watch all my projects" — the full in-scope set. */
  protected watchAll(): void {
    const keys = this.allProjects().map((p) => p.project_key);
    const anchor = this.forecastQueue()[0]?.project_key ?? keys[0] ?? '';
    this.warnTarget.set({ type: 'group', key: '__all__', name: 'All my projects', projectKeys: keys, anchor });
    this.loadWarnings();
  }

  private chooseTarget(t: PredictTarget): void {
    if (this.subview() === 'warnings') {
      this.warnTarget.set(t);
      this.loadWarnings();
    } else if (this.subview() === 'forecasts') {
      this.selectForecastSubject(t);
    } else {
      this.scTargetSel.set(t);
      this.resetScenario();
    }
  }
  protected isActiveTarget(type: 'project' | 'group', key: string): boolean {
    const t = this.subview() === 'warnings' ? this.warnTarget()
      : this.subview() === 'forecasts' ? this.fcSubject()
      : this.scTargetSel();
    return !!t && t.type === type && t.key === key;
  }

  // --- forecasts (subject → tracked instances) ---
  /** Pick a project/group as the forecast subject and load its past instances. */
  protected selectForecastSubject(t: PredictTarget): void {
    this.fcSubject.set(t);
    this.resetForecast();
    this.fcCompare.set(new Set());
    this.resetForecastScope();
    this.loadForecastInstances();
  }
  /** Return to the subject selector. */
  protected changeForecastSubject(): void {
    this.fcSubject.set(null);
    this.fcInstances.set([]);
    this.fcInstancesError.set(null);
    this.fcCompare.set(new Set());
    this.resetForecast();
    this.resetForecastScope();
  }

  // --- forecast sub-scope (project | release | component | tag) ---
  /** Reset the sub-scope back to whole-project (called on every subject change). */
  private resetForecastScope(): void {
    this.fcScope.set('project');
    this.fcScopeValue.set(null);
    this.fcFacetFilter.set('');
    this.fcSubjects.set(null);
    this.fcSubjectsError.set(null);
  }
  /** Switch the sub-scope; loads the project's facets lazily for release/component/tag. */
  protected setForecastScope(scope: FcScope): void {
    if (this.fcScope() === scope) return;
    this.fcScope.set(scope);
    this.fcScopeValue.set(null);
    this.fcFacetFilter.set('');
    if (scope !== 'project') this.loadForecastSubjects();
  }
  /** Choose a facet value (a specific release/component/tag) as the forecast scope. */
  protected selectScopeValue(value: string): void { this.fcScopeValue.set(value); }
  /** Clear back to whole-project without leaving the subject. */
  protected clearForecastScope(): void {
    this.fcScope.set('project');
    this.fcScopeValue.set(null);
    this.fcFacetFilter.set('');
  }

  private loadForecastSubjects(): void {
    const t = this.fcSubject();
    if (!t || t.type !== 'project') return;
    const key = t.key;
    const cached = this.subjectsCache.get(key);
    if (cached) { this.fcSubjects.set(cached); return; }
    this.fcSubjectsLoading.set(true);
    this.fcSubjectsError.set(null);
    this.projectsService.getForecastSubjects(key).subscribe({
      next: (r) => { this.subjectsCache.set(key, r); this.fcSubjects.set(r); this.fcSubjectsLoading.set(false); },
      error: () => { this.fcSubjectsError.set('Unable to load release/component/tag facets for this project.'); this.fcSubjectsLoading.set(false); },
    });
  }
  /** Focus the Forecasts view on a specific project (e.g. handed off from history). */
  protected selectForecastProject(key: string): void {
    this.selectForecastSubject(this.targetFromProjectKey(key));
  }

  private loadForecastInstances(): void {
    const t = this.fcSubject();
    if (!t) return;
    this.fcInstancesLoading.set(true);
    this.fcInstancesError.set(null);
    const keys = new Set(t.projectKeys);
    this.risk.listForecasts({ scope: this.scope.userKey() || null, limit: 100 }).subscribe({
      next: (page) => {
        const rows = page.items
          .filter((r) => keys.has(r.project_key))
          .sort((a, b) => (a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0));
        this.fcInstances.set(rows);
        this.fcInstancesLoading.set(false);
      },
      error: () => { this.fcInstancesError.set('Unable to load past forecasts for this subject.'); this.fcInstancesLoading.set(false); },
    });
  }

  /** Run a new forecast on the subject's anchor; prepend the row and show its briefing. */
  protected runForecastForSubject(): void {
    const t = this.fcSubject();
    if (!t || this.fcNeedsScopeValue()) return;
    const scope = this.fcScope();
    const value = this.fcScopeValue();
    // Sub-scope only applies to a whole-project subject; groups stay project-anchored.
    if (t.type === 'project' && scope !== 'project' && value) {
      this.runForecast(t.anchor, { subjectType: scope, subjectValue: value });
    } else {
      this.runForecast(t.anchor);
    }
  }

  protected runForecast(
    projectKey: string,
    subject: { subjectType?: string; subjectValue?: string } = {},
  ): void {
    if (!projectKey || this.forecasting()) return;
    this.fcTarget = projectKey;
    this.forecasting.set(true);
    this.fcError.set(null);
    this.forecast.set(null);
    this.activeForecastId.set(null);
    this.risk.runForecast(projectKey, this.scope.userKey() || 'director', subject).subscribe({
      next: (f) => {
        this.forecast.set(f);
        this.forecasting.set(false);
        this.activeForecastId.set(f.forecast_id);
        if (this.fcSubject()) this.prependInstance(f);
      },
      error: () => { this.fcError.set('The Forecast Agent could not run. Is RiskAnalytics-API on :8004 up (ANTHROPIC_API_KEY set)?'); this.forecasting.set(false); },
    });
  }

  /** Open one past forecast instance in the briefing (no navigation). */
  protected viewInstance(id: string): void {
    if (this.forecasting()) return;
    this.forecasting.set(true);
    this.fcError.set(null);
    this.forecast.set(null);
    this.activeForecastId.set(null);
    this.risk.getForecast(id).subscribe({
      next: (f) => { this.forecast.set(f); this.fcTarget = f.project_key; this.activeForecastId.set(f.forecast_id); this.forecasting.set(false); },
      error: () => { this.fcError.set('Unable to load that forecast.'); this.forecasting.set(false); },
    });
  }

  /** Fold a freshly-run full forecast into the instances table as a summary row. */
  private prependInstance(f: Forecast): void {
    const row: ForecastSummary = {
      forecast_id: f.forecast_id,
      project_key: f.project_key,
      on_time_probability: f.on_time_probability,
      outlook: f.outlook,
      projected_slip_days_low: f.projected_slip_days_low,
      projected_slip_days_high: f.projected_slip_days_high,
      confidence: f.confidence,
      status: f.status,
      created_at: f.created_at,
      subject_type: f.subject_type,
      subject_value: f.subject_value,
    };
    this.fcInstances.update((rows) => [row, ...rows.filter((r) => r.forecast_id !== f.forecast_id)]);
  }

  protected resetForecast(): void { this.forecast.set(null); this.fcError.set(null); this.activeForecastId.set(null); }

  // --- forecast compare (A/B over two instances) ---
  protected toggleCompare(id: string): void {
    this.fcCompare.update((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else if (n.size < 2) n.add(id);
      return n;
    });
  }
  protected isCompared(id: string): boolean { return this.fcCompare().has(id); }
  protected get fcCompareCount(): number { return this.fcCompare().size; }
  protected clearCompare(): void { this.fcCompare.set(new Set()); }

  private outlookRank(o: string | null | undefined): number {
    return o === 'on_track' ? 2 : o === 'at_risk' ? 1 : o === 'off_track' ? 0 : 1;
  }
  /** The two selected instances, ordered older → newer, with computed deltas. */
  protected readonly compareDelta = computed<ForecastDelta | null>(() => {
    const sel = this.fcCompare();
    if (sel.size !== 2) return null;
    const pair = this.fcInstances()
      .filter((r) => sel.has(r.forecast_id))
      .sort((a, b) => (a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0));
    if (pair.length !== 2) return null;
    const [a, b] = pair;
    const onTimeA = this.pct(a.on_time_probability), onTimeB = this.pct(b.on_time_probability);
    const confA = this.pct(a.confidence), confB = this.pct(b.confidence);
    const ra = this.outlookRank(a.outlook), rb = this.outlookRank(b.outlook);
    return {
      a, b,
      onTimeA, onTimeB, onTimeDelta: onTimeB - onTimeA,
      confA, confB, confDelta: confB - confA,
      outlookChanged: (a.outlook || '') !== (b.outlook || ''),
      outlookImproved: rb === ra ? null : rb > ra,
    };
  });
  protected outlookLabel(o: string | null | undefined): string { return (o || '—').replace('_', ' '); }
  protected signedNum(n: number): string { return (n > 0 ? '+' : '') + n; }

  // --- scenarios ---
  /** Focus the Scenarios view on a project (e.g. handed off from a forecast). */
  protected selectScenarioProject(key: string): void {
    this.scTargetSel.set(this.targetFromProjectKey(key));
    this.resetScenario();
  }
  /** Return to the target selector to re-scope the what-if. */
  protected changeScenarioTarget(): void {
    this.scTargetSel.set(null);
    this.resetScenario();
  }

  protected runScenario(): void {
    const t = this.scTargetSel();
    const text = this.scText.trim();
    if (!t || !text || this.simulating()) return;
    this.simulating.set(true);
    this.scError.set(null);
    this.scenario.set(null);
    this.scResultTarget.set(t);
    this.risk.runScenario(t.anchor, text, this.scope.userKey() || 'director').subscribe({
      next: (s) => { this.scenario.set(s); this.simulating.set(false); },
      error: () => { this.scError.set('The Scenario Simulator could not run. Is RiskAnalytics-API on :8004 up (ANTHROPIC_API_KEY set)?'); this.simulating.set(false); },
    });
  }
  protected runProbe(p: ScenarioProbe): void { this.scText = p.text; this.runScenario(); }
  protected resetScenario(): void { this.scenario.set(null); this.scError.set(null); this.scText = ''; }

  // --- custom probes (persisted) ---
  private loadCustomProbes(): ScenarioProbe[] {
    try {
      const raw = localStorage.getItem(Predict.PROBES_KEY);
      if (!raw) return [];
      const parsed: unknown = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.filter(
        (p): p is ScenarioProbe => !!p && typeof p === 'object'
          && typeof (p as ScenarioProbe).label === 'string'
          && typeof (p as ScenarioProbe).text === 'string',
      );
    } catch { return []; }
  }
  private persistCustomProbes(): void {
    try { localStorage.setItem(Predict.PROBES_KEY, JSON.stringify(this.customProbes())); } catch { /* storage unavailable */ }
  }
  protected addCustomProbe(): void {
    const text = this.newProbe.trim();
    if (!text) return;
    const label = text.length > 32 ? text.slice(0, 30).trimEnd() + '…' : text;
    this.customProbes.update((list) => [...list, { label, text }]);
    this.persistCustomProbes();
    this.newProbe = '';
  }
  protected removeCustomProbe(p: ScenarioProbe): void {
    this.customProbes.update((list) => list.filter((x) => x !== p));
    this.persistCustomProbes();
  }

  // --- early-warnings ---
  protected changeWarnTarget(): void { this.warnTarget.set(null); this.warnings.set([]); this.warningsError.set(null); }
  private loadWarnings(): void {
    const t = this.warnTarget();
    if (!t) return;
    this.warningsLoading.set(true);
    this.warningsError.set(null);
    const scope = t.projectKeys.join(',') || null;
    this.risk.getEarlyWarnings(scope, 15).subscribe({
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
    // Selected criteria filter SERVER-side via the `projects` param (groups expanded to members).
    const projects = [...this.histFilterKeys()];
    const opts = { scope: this.scope.userKey() || null, q: this.histQuery, limit: this.pageSize, offset: this.offset, projects };
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

  // --- history criteria filter (server-side, via the `projects` param) ---
  protected toggleHistCriterion(id: string): void {
    this.histSel.update((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
    this.reloadHistory();
  }
  protected isHistSelected(id: string): boolean { return this.histSel().has(id); }
  protected clearHistCriteria(): void { this.histSel.set(new Set()); this.reloadHistory(); }
  protected get histCriteriaCount(): number { return this.histSel().size; }

  /** Union of project keys implied by the selected criteria (projects + groups' members). */
  private readonly histFilterKeys = computed<ReadonlySet<string>>(() => {
    const sel = this.histSel();
    if (!sel.size) return new Set();
    const keys = new Set<string>();
    for (const id of sel) {
      if (id.startsWith('p:')) keys.add(id.slice(2));
      else if (id.startsWith('g:')) {
        this.groups().find((g) => g.group_key === id.slice(2))?.project_keys.forEach((k) => keys.add(k));
      }
    }
    return keys;
  });
  protected nextPage(): void { if (this.offset + this.pageSize < this.histTotal()) { this.offset += this.pageSize; this.loadHistory(); } }
  protected prevPage(): void { if (this.offset > 0) { this.offset = Math.max(0, this.offset - this.pageSize); this.loadHistory(); } }
  protected get pageStart(): number { return this.histTotal() === 0 ? 0 : this.offset + 1; }
  protected get pageEnd(): number { return Math.min(this.offset + this.pageSize, this.histTotal()); }
  protected get canPrev(): boolean { return this.offset > 0; }
  protected get canNext(): boolean { return this.offset + this.pageSize < this.histTotal(); }

  protected openForecast(id: string): void {
    this.router.navigate(['/predict/forecasts']);
    this.forecasting.set(true); this.fcError.set(null); this.forecast.set(null); this.activeForecastId.set(null);
    this.fcCompare.set(new Set());
    this.risk.getForecast(id).subscribe({
      next: (f) => {
        this.forecast.set(f);
        this.fcTarget = f.project_key;
        this.activeForecastId.set(f.forecast_id);
        this.fcSubject.set(this.targetFromProjectKey(f.project_key));
        this.loadForecastInstances();
        this.forecasting.set(false);
      },
      error: () => { this.fcError.set('Unable to load that forecast.'); this.forecasting.set(false); },
    });
  }
  protected openScenario(id: string): void {
    this.router.navigate(['/predict/scenarios']);
    this.simulating.set(true); this.scError.set(null); this.scenario.set(null);
    this.risk.getScenario(id).subscribe({
      next: (s) => {
        this.scenario.set(s);
        const t = this.targetFromProjectKey(s.project_key);
        this.scTargetSel.set(t);
        this.scResultTarget.set(t);
        this.simulating.set(false);
      },
      error: () => { this.scError.set('Unable to load that scenario.'); this.simulating.set(false); },
    });
  }

  // --- formatting ---
  /** True when a forecast was scoped to a release/component/tag (not the whole project). */
  protected isSubScoped(t: string | null | undefined): boolean { return !!t && t !== 'project'; }
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
