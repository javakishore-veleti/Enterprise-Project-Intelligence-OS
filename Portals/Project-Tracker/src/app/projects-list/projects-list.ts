import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { PortfolioProject, PortfolioSummary } from '../models/portfolio';
import { ProjectsService } from '../services/projects.service';
import { About } from '../ui/about';
import { UserScopeService } from '../ui/user-scope.service';

@Component({
  selector: 'app-projects-list',
  imports: [FormsModule, RouterLink, DecimalPipe, About],
  templateUrl: './projects-list.html',
  styleUrl: './projects-list.css',
})
export class ProjectsList {
  private readonly projectsService = inject(ProjectsService);
  protected readonly scope = inject(UserScopeService);

  protected readonly summary = signal<PortfolioSummary | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected view: 'cards' | 'table' = 'table';
  protected asOf = '';
  protected query = '';
  protected readonly todayStr = this.isoDate(0);

  /** Projects in scope, filtered by the search query. */
  protected readonly projects = computed<PortfolioProject[]>(() => {
    const all = this.summary()?.top_projects ?? [];
    const q = this.query.trim().toLowerCase();
    return q ? all.filter((p) => p.project_key.toLowerCase().includes(q) || (p.name || '').toLowerCase().includes(q)) : all;
  });
  protected readonly totals = computed(() => this.summary()?.totals ?? { projects: 0, issues: 0, open_issues: 0 });
  protected readonly bands = computed(() => this.summary()?.risk_bands ?? { high: 0, medium: 0, low: 0, unscored: 0 });

  constructor() {
    toObservable(this.scope.userKey).subscribe(() => this.load());
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.projectsService.getPortfolioSummary(50, this.scope.userKey() || null, this.asOf || undefined).subscribe({
      next: (s) => { this.summary.set(s); this.loading.set(false); },
      error: () => { this.error.set('Unable to load projects. Is the Projects-API running on :8003?'); this.loading.set(false); },
    });
  }

  protected onDateChange(): void { this.load(); }
  protected setToday(): void { this.asOf = ''; this.load(); }
  protected setYesterday(): void { this.asOf = this.isoDate(-1); this.load(); }
  protected get isToday(): boolean { return this.asOf === '' || this.asOf === this.todayStr; }

  protected bandClass(band: string): string { return (band || 'low').toLowerCase(); }
  protected scoreClass(score: number): string { return score >= 66 ? 'high' : score >= 33 ? 'medium' : 'low'; }
  protected pctOf(v: number): number { return Math.round((v ?? 0) * 100); }

  private isoDate(days: number): string { const d = new Date(); d.setDate(d.getDate() + days); return d.toISOString().slice(0, 10); }
}
