import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged, startWith, switchMap } from 'rxjs/operators';

import { Project } from '../models/project';
import { ProjectsService } from '../services/projects.service';
import { About } from '../ui/about';

@Component({
  selector: 'app-projects-list',
  imports: [FormsModule, RouterLink, About],
  templateUrl: './projects-list.html',
  styleUrl: './projects-list.css',
})
export class ProjectsList implements OnInit, OnDestroy {
  protected readonly projects = signal<Project[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  query = '';

  private readonly search$ = new Subject<string>();
  private sub?: Subscription;

  /** Portfolio KPIs computed from the loaded projects. */
  protected readonly totalIssues = computed(() =>
    this.projects().reduce((s, p) => s + (p.issue_count ?? 0), 0),
  );
  protected readonly totalOpen = computed(() =>
    this.projects().reduce((s, p) => s + (p.open_issue_count ?? 0), 0),
  );
  protected readonly openRatio = computed(() => {
    const t = this.totalIssues();
    return t > 0 ? this.totalOpen() / t : 0;
  });
  protected readonly atRisk = computed(() =>
    this.projects().filter((p) => (p.issue_count ?? 0) > 0 && (p.open_issue_count ?? 0) / (p.issue_count ?? 1) >= 0.5).length,
  );

  constructor(private readonly projectsService: ProjectsService) {}

  ngOnInit(): void {
    this.sub = this.search$
      .pipe(
        startWith(this.query),
        debounceTime(300),
        distinctUntilChanged(),
        switchMap((query) => {
          this.loading.set(true);
          this.error.set(null);
          return this.projectsService.searchProjects({ query: query.trim(), limit: 50 });
        }),
      )
      .subscribe({
        next: (response) => {
          this.projects.set(response.items);
          this.total.set(response.page.total);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Unable to load projects. Is the Projects-API running on :8003?');
          this.projects.set([]);
          this.total.set(0);
          this.loading.set(false);
        },
      });
  }

  onQueryChange(value: string): void {
    this.search$.next(value);
  }

  /** Open-issue ratio for one project (0–1), for the inline health bar. */
  protected ratio(p: Project): number {
    const issues = p.issue_count ?? 0;
    return issues > 0 ? (p.open_issue_count ?? 0) / issues : 0;
  }

  protected healthClass(p: Project): string {
    const r = this.ratio(p);
    return r >= 0.5 ? 'is-high' : r >= 0.25 ? 'is-medium' : 'is-low';
  }

  protected asPercent(v: number): string {
    return `${Math.round(v * 100)}%`;
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}
