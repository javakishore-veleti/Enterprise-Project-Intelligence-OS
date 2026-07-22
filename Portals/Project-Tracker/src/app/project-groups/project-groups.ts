import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Project } from '../models/project';
import { ProjectGroup } from '../models/group';
import { GroupsService } from '../services/groups.service';
import { ProjectsService } from '../services/projects.service';
import { RiskAnalyticsService } from '../services/risk-analytics.service';
import { NotificationService } from '../ui/notification.service';

@Component({
  selector: 'app-project-groups',
  imports: [FormsModule],
  templateUrl: './project-groups.html',
  styleUrl: './project-groups.css',
})
export class ProjectGroups implements OnInit {
  private readonly groupsService = inject(GroupsService);
  private readonly projectsService = inject(ProjectsService);
  private readonly riskService = inject(RiskAnalyticsService);
  private readonly notify = inject(NotificationService);

  protected readonly groups = signal<ProjectGroup[]>([]);
  protected readonly projects = signal<Project[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly saving = signal(false);
  protected readonly runningKey = signal<string | null>(null);

  // Create-form state.
  protected showForm = false;
  protected formName = '';
  protected formDescription = '';
  protected readonly selected = signal<Set<string>>(new Set());

  protected readonly canCreate = computed(() => this.formName.trim().length > 0 && this.selected().size > 0);

  ngOnInit(): void {
    this.reload();
    this.projectsService.searchProjects({ limit: 200 }).subscribe({
      next: (r) => this.projects.set(r.items),
      error: () => {},
    });
  }

  private reload(): void {
    this.loading.set(true);
    this.groupsService.list().subscribe({
      next: (r) => { this.groups.set(r.items); this.loading.set(false); this.error.set(null); },
      error: () => {
        this.loading.set(false);
        this.error.set('Unable to load groups. Is the Projects-API running on :8003?');
      },
    });
  }

  protected toggleForm(): void {
    this.showForm = !this.showForm;
    if (!this.showForm) this.resetForm();
  }

  protected isSelected(key: string): boolean {
    return this.selected().has(key);
  }

  protected toggleProject(key: string): void {
    this.selected.update((s) => {
      const next = new Set(s);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  protected create(): void {
    if (!this.canCreate() || this.saving()) return;
    this.saving.set(true);
    this.groupsService
      .create({ name: this.formName.trim(), description: this.formDescription.trim(), project_keys: [...this.selected()] })
      .subscribe({
        next: (g) => {
          this.saving.set(false);
          this.resetForm();
          this.showForm = false;
          this.notify.success('Group created', `"${g.name}" with ${g.project_keys.length} project(s).`);
          this.reload();
        },
        error: (e) => {
          this.saving.set(false);
          this.notify.error('Could not create group', e?.status === 409 ? 'A group with that name already exists.' : 'The Projects-API rejected the request.');
        },
      });
  }

  protected async remove(g: ProjectGroup): Promise<void> {
    const ok = await this.notify.confirm({
      title: 'Delete group?',
      message: `Delete "${g.name}"? This removes the group only — the projects themselves are untouched.`,
      confirmLabel: 'Delete',
      danger: true,
    });
    if (!ok) return;
    this.groupsService.remove(g.group_key).subscribe({
      next: () => { this.notify.success('Group deleted', `"${g.name}" removed.`); this.reload(); },
      error: () => this.notify.error('Delete failed', 'The Projects-API did not remove the group.'),
    });
  }

  protected async runPortfolio(g: ProjectGroup): Promise<void> {
    const ok = await this.notify.confirm({
      title: 'Run portfolio risk?',
      message: `Run combined multi-agent risk analysis across the ${g.project_keys.length} project(s) in "${g.name}" via live LLM calls (may take a minute).`,
      confirmLabel: 'Run portfolio risk',
    });
    if (!ok) return;
    this.runningKey.set(g.group_key);
    this.notify.info('Portfolio analysis started', `Combining risk across "${g.name}"…`);
    this.riskService
      .startPortfolioAnalysis(g.group_key, {
        agents: ['schedule_risk', 'quality_risk', 'backlog_health'],
        projectKeys: g.project_keys,
        requestedBy: 'project-tracker-ui',
      })
      .subscribe({
        next: (run) => {
          this.runningKey.set(null);
          this.notify.success('Portfolio analysis complete', `${run.findings.length} combined finding(s) across "${g.name}".`);
        },
        error: () => {
          this.runningKey.set(null);
          this.notify.error('Portfolio analysis failed', 'Check the RiskAnalytics-API on :8004 and ANTHROPIC_API_KEY.');
        },
      });
  }

  private resetForm(): void {
    this.formName = '';
    this.formDescription = '';
    this.selected.set(new Set());
  }

  protected projectName(key: string): string {
    return this.projects().find((p) => p.project_key === key)?.name ?? key;
  }
}
