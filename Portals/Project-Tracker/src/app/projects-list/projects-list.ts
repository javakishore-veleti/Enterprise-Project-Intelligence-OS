import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged, startWith, switchMap } from 'rxjs/operators';

import { Project } from '../models/project';
import { ProjectsService } from '../services/projects.service';

@Component({
  selector: 'app-projects-list',
  imports: [FormsModule],
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

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}
