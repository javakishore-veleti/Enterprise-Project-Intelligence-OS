import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, map } from 'rxjs/operators';

import { Decision, DecisionOption, DecisionSummary } from '../models/analysis';
import { ProjectGroup } from '../models/group';
import { PortfolioProject, PortfolioSummary, ProjectSearchItem } from '../models/portfolio';
import { GroupsService } from '../services/groups.service';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';
import { NotificationService } from '../ui/notification.service';
import { About } from '../ui/about';
import { UserScopeService } from '../ui/user-scope.service';

type Sub = 'options' | 'plan' | 'decisions';

/**
 * The subject a Decide view is scoped to. `anchor` is the single project the
 * agent actually runs the decision against — its own key for a project, or the
 * highest-risk member for a group (a group decides on its most-at-risk project).
 */
interface DecideTarget {
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

/**
 * Decide = the commitment surface. Predict projects and explores; Decide leads
 * with OPTIONS the agent proposes, lets you choose one, expands the choice into a
 * prioritized plan, and approves it as a dry-run/preview (no external tickets).
 * Three views: Options (generate + compare), Plan (the selected option, approve),
 * and Decisions (persisted history).
 */
@Component({
  selector: 'app-decide',
  imports: [FormsModule, RouterLink, DecimalPipe, NgTemplateOutlet, About],
  templateUrl: './decide.html',
  styleUrl: './decide.css',
})
export class Decide {
  private readonly projectsService = inject(ProjectsService);
  private readonly groupsService = inject(GroupsService);
  private readonly risk = inject(RiskAnalyticsService);
  private readonly notifications = inject(NotificationService);
  protected readonly scope = inject(UserScopeService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly subview = toSignal(
    this.route.paramMap.pipe(
      map((p) => {
        const v = p.get('view');
        return v === 'plan' || v === 'decisions' ? v : 'options';
      }),
    ),
    { initialValue: 'options' as Sub },
  );

  // project list (for the target selector)
  protected readonly summary = signal<PortfolioSummary | null>(null);
  protected readonly groups = signal<ProjectGroup[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly allProjects = computed<PortfolioProject[]>(() => this.summary()?.top_projects ?? []);

  /** Top-10 at-risk projects (highest risk first) — the natural decide candidates. */
  protected readonly decideQueue = computed<PortfolioProject[]>(() =>
    this.allProjects().filter((p) => p.risk_score != null).slice(0, 10),
  );

  /** Project-group cards with rolled-up (max/avg) member risk + highest-risk anchor. */
  protected readonly groupCards = computed<GroupCard[]>(() =>
    this.groups().map((g) => ({ group: g, ...this.groupRisk(g) })),
  );

  // ---- server-backed project search (Options selector) ----
  /** Search box text; empty → the selector shows the summary's top projects (default). */
  protected readonly projQuery = signal('');
  protected readonly searchResults = signal<ProjectSearchItem[]>([]);
  protected readonly searchTotal = signal(0);
  protected readonly searchLoading = signal(false);
  protected readonly searchLoadingMore = signal(false);
  protected readonly searchError = signal<string | null>(null);
  private searchOffset = 0;
  private readonly searchPageSize = 24;
  protected readonly searchActive = computed(() => this.projQuery().trim().length > 0);
  protected readonly canLoadMoreProjects = computed(() => this.searchResults().length < this.searchTotal());

  // ---- decision state (shared across Options + Plan) ----
  /** The project/group the current decision is scoped to (null → show selector). */
  protected readonly decTarget = signal<DecideTarget | null>(null);
  /** The loaded/generated decision (its options, selection, status). */
  protected readonly decision = signal<Decision | null>(null);
  protected readonly generating = signal(false);
  protected readonly decError = signal<string | null>(null);
  protected readonly selecting = signal<string | null>(null);
  protected readonly approving = signal(false);

  /** A `?project=` key arriving from Predict's "Take to Decide", applied once projects load. */
  private pendingPreselect: string | null = null;

  // ---- decisions history state ----
  protected readonly history = signal<DecisionSummary[]>([]);
  protected readonly histTotal = signal(0);
  protected readonly histLoading = signal(false);
  protected readonly histError = signal<string | null>(null);
  protected histQuery = '';
  protected readonly pageSize = 20;
  protected readonly maxRows = 100;
  protected offset = 0;

  /** The option currently selected on the loaded decision (drives the Plan view). */
  protected readonly selectedOption = computed<DecisionOption | null>(() => {
    const d = this.decision();
    if (!d || !d.selected_option_id) return null;
    return d.options.find((o) => o.option_id === d.selected_option_id) ?? null;
  });

  /** Rolled-up risk score of the current subject (project score or group max). */
  protected readonly targetRisk = computed<number | null>(() => {
    const t = this.decTarget();
    if (!t) return null;
    if (t.type === 'project') return this.projectByKey(t.key)?.risk_score ?? null;
    const g = this.groups().find((x) => x.group_key === t.key);
    return g ? this.groupRisk(g).max : null;
  });

  constructor() {
    this.loadGroups();
    this.load();
    toObservable(this.scope.userKey).subscribe(() => {
      this.load();
      if (this.searchActive()) this.runProjectSearch(this.projQuery().trim());
      if (this.subview() === 'decisions') this.reloadHistory();
    });
    toObservable(this.subview).subscribe((v) => {
      if (v === 'decisions') this.reloadHistory();
    });
    // Debounced server-backed project search for the Options card selector.
    toObservable(this.projQuery)
      .pipe(debounceTime(300))
      .subscribe((q) => this.runProjectSearch(q.trim()));
    this.route.queryParamMap.subscribe((qp) => {
      const proj = qp.get('project');
      if (proj) { this.pendingPreselect = proj; this.applyPreselect(); }
    });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.projectsService.getPortfolioSummary(50, this.scope.userKey() || null).subscribe({
      next: (s) => { this.summary.set(s); this.loading.set(false); this.applyPreselect(); },
      error: () => { this.error.set('Unable to load projects. Is the Projects-API running on :8003?'); this.loading.set(false); },
    });
  }

  private loadGroups(): void {
    this.groupsService.list().subscribe({
      next: (r) => this.groups.set(r.items),
      error: () => this.groups.set([]),
    });
  }

  /** Preselect the `?project=` subject once projects are available (from Predict handoff). */
  private applyPreselect(): void {
    const key = this.pendingPreselect;
    if (!key || this.decTarget() || this.decision()) return;
    if (!this.allProjects().length) return;
    this.decTarget.set(this.targetFromProjectKey(key));
    this.pendingPreselect = null;
  }

  protected projectName(key: string): string {
    return this.allProjects().find((p) => p.project_key === key)?.name || key;
  }

  // ---- target selector (shared with predict pattern) ----
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

  private targetFromProject(p: PortfolioProject): DecideTarget {
    return { type: 'project', key: p.project_key, name: p.name || p.project_key, projectKeys: [p.project_key], anchor: p.project_key };
  }
  private targetFromProjectKey(key: string): DecideTarget {
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

  private targetFromSearchItem(it: ProjectSearchItem): DecideTarget {
    return { type: 'project', key: it.project_key, name: it.name || it.project_key, projectKeys: [it.project_key], anchor: it.project_key };
  }
  /** Pick a searched project card — scopes the decision exactly like a summary card. */
  protected pickSearchItem(it: ProjectSearchItem): void { this.chooseTarget(this.targetFromSearchItem(it)); }
  /** Risk band CSS class for a search item (null risk_score → 'none'). */
  protected searchRiskClass(score: number | null): string {
    return score == null ? 'none' : this.riskScoreClass(score);
  }

  /** Pick a project card in the selector — scopes the decision to it. */
  protected pickProject(p: PortfolioProject): void { this.chooseTarget(this.targetFromProject(p)); }
  /** Pick a group card in the selector — scopes the decision to its highest-risk member. */
  protected pickGroup(gc: GroupCard): void {
    this.chooseTarget({ type: 'group', key: gc.group.group_key, name: gc.group.name, projectKeys: [...gc.group.project_keys], anchor: gc.anchor });
  }
  private chooseTarget(t: DecideTarget): void {
    this.decTarget.set(t);
    this.resetDecision();
  }
  protected isActiveTarget(type: 'project' | 'group', key: string): boolean {
    const t = this.decTarget();
    return !!t && t.type === type && t.key === key;
  }
  /** Return to the subject selector, clearing any generated options. */
  protected changeTarget(): void {
    this.decTarget.set(null);
    this.resetDecision();
  }
  private resetDecision(): void {
    this.decision.set(null);
    this.decError.set(null);
    this.selecting.set(null);
    this.approving.set(false);
  }

  // ---- options: generate ----
  /** Ask the Decide agent to generate options for the current subject's anchor. */
  protected generateOptions(): void {
    const t = this.decTarget();
    if (!t || this.generating()) return;
    this.generating.set(true);
    this.decError.set(null);
    this.decision.set(null);
    this.risk.runDecision(t.anchor, this.scope.userKey() || 'director').subscribe({
      next: (d) => { this.decision.set(d); this.generating.set(false); },
      error: () => { this.decError.set('The Decide Agent could not run. Is RiskAnalytics-API on :8004 up (ANTHROPIC_API_KEY set)?'); this.generating.set(false); },
    });
  }

  protected isSelected(o: DecisionOption): boolean {
    return this.decision()?.selected_option_id === o.option_id;
  }

  // ---- options: choose one → plan ----
  protected chooseOption(o: DecisionOption): void {
    const d = this.decision();
    if (!d || this.selecting()) return;
    this.selecting.set(o.option_id);
    this.decError.set(null);
    this.risk.selectOption(d.decision_id, o.option_id).subscribe({
      next: (updated) => {
        this.decision.set(updated);
        this.selecting.set(null);
        this.router.navigate(['/decide/plan']);
      },
      error: () => { this.decError.set('Unable to select that option. Is RiskAnalytics-API on :8004 up?'); this.selecting.set(null); },
    });
  }

  // ---- plan: approve (dry-run confirmation) ----
  protected async approve(): Promise<void> {
    const d = this.decision();
    if (!d || this.approving()) return;
    const ok = await this.notifications.confirm({
      title: 'Approve & act — dry-run preview',
      message:
        'This approves the selected option as a preview only. No external tickets, ' +
        'assignments or messages are created — the plan is recorded so the team can act on it. Approve now?',
      confirmLabel: 'Approve (dry-run)',
      cancelLabel: 'Not yet',
    });
    if (!ok) return;
    this.approving.set(true);
    this.decError.set(null);
    this.risk.approveDecision(d.decision_id).subscribe({
      next: (updated) => {
        this.decision.set(updated);
        this.approving.set(false);
        this.notifications.success('Decision approved', `${updated.project_key} — plan recorded as a dry-run preview.`);
      },
      error: () => { this.decError.set('Unable to approve this decision. Is RiskAnalytics-API on :8004 up?'); this.approving.set(false); },
    });
  }

  // ---- decisions history ----
  private reloadHistory(): void { this.offset = 0; this.loadHistory(); }
  protected loadHistory(): void {
    this.histLoading.set(true);
    this.histError.set(null);
    this.risk.listDecisions({ scope: this.scope.userKey() || null, q: this.histQuery, limit: this.pageSize, offset: this.offset }).subscribe({
      next: (page) => { this.history.set(page.items); this.histTotal.set(Math.min(page.total, this.maxRows)); this.histLoading.set(false); },
      error: () => { this.histError.set('Unable to load decision history.'); this.histLoading.set(false); },
    });
  }
  protected searchHistory(): void { this.reloadHistory(); }
  protected nextPage(): void { if (this.offset + this.pageSize < this.histTotal()) { this.offset += this.pageSize; this.loadHistory(); } }
  protected prevPage(): void { if (this.offset > 0) { this.offset = Math.max(0, this.offset - this.pageSize); this.loadHistory(); } }
  protected get pageStart(): number { return this.histTotal() === 0 ? 0 : this.offset + 1; }
  protected get pageEnd(): number { return Math.min(this.offset + this.pageSize, this.histTotal()); }
  protected get canPrev(): boolean { return this.offset > 0; }
  protected get canNext(): boolean { return this.offset + this.pageSize < this.histTotal(); }

  /** Open a past decision — load it, scope to its project, route to plan (if chosen) or options. */
  protected openDecision(id: string): void {
    this.generating.set(true);
    this.decError.set(null);
    this.decision.set(null);
    this.risk.getDecision(id).subscribe({
      next: (d) => {
        this.decision.set(d);
        this.decTarget.set(this.targetFromProjectKey(d.project_key));
        this.generating.set(false);
        this.router.navigate([d.selected_option_id ? '/decide/plan' : '/decide/options']);
      },
      error: () => { this.decError.set('Unable to load that decision.'); this.generating.set(false); },
    });
  }

  // ---- formatting ----
  protected pct(v: number | null | undefined): number { return Math.round((v ?? 0) * 100); }
  protected confClass(v: number | null | undefined): string {
    const p = this.pct(v);
    return p >= 66 ? 'low' : p >= 40 ? 'medium' : 'high';
  }
  protected riskScoreClass(score: number): string { return score >= 66 ? 'high' : score >= 33 ? 'medium' : 'low'; }
  /** Status badge tone: DRAFTED=slate, SELECTED=azure, APPROVED=green, FAILED=red. */
  protected statusClass(s: string): string { return (s || 'drafted').toLowerCase(); }
}
