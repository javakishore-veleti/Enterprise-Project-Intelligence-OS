import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import {
  AddGrantRequest,
  AddTrackerProjectsRequest,
  CreateRepositoryRequest,
  GRANT_DIRECTIONS,
  Grant,
  GrantDirection,
  PROVIDER_LABELS,
  PROVIDERS,
  Provider,
  Repository,
  TrackerProject,
  VISIBILITY_HINTS,
  VISIBILITY_SCOPES,
  VisibilityScope,
} from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';
import { NotificationService } from '../../ui/notification.service';
import { OrgPicker } from '../org-picker/org-picker';

/** Page sizes offered by the selectors — bounded regardless of total. */
const PAGE_SIZES = [25, 50, 100] as const;

/**
 * Repositories & Visibility page (route: /organizations/repositories).
 * Standalone, full-width, operating on the shared selected-org context.
 *
 * The repository list is SERVER-PAGED + SEARCHABLE (`q` on provider /
 * external_account) — only the current page of repos is rendered
 * (page-replacement), so an org with many connected repos stays bounded.
 * Selecting a repo loads its tracker projects and grants from the paginated
 * list endpoints (a repo can carry thousands of projects), each with its own
 * bounded-DOM pager — NOT session-only chips of just what was added this visit.
 */
@Component({
  selector: 'app-org-repositories',
  imports: [FormsModule, OrgPicker],
  templateUrl: './org-repositories.html',
  styleUrls: ['../org.css'],
})
export class OrgRepositories {
  private readonly orgAdmin = inject(OrgAdminService);
  protected readonly ctx = inject(OrgContextService);
  private readonly notifications = inject(NotificationService);
  private lastId: string | null = null;

  protected readonly providers = PROVIDERS;
  protected readonly providerLabels = PROVIDER_LABELS;
  protected readonly visibilityScopes = VISIBILITY_SCOPES;
  protected readonly visibilityHints = VISIBILITY_HINTS;
  protected readonly grantDirections = GRANT_DIRECTIONS;
  protected readonly pageSizes = PAGE_SIZES;

  // --- Repository list (bounded, page-replacement) --------------------------
  protected readonly repositories = signal<Repository[]>([]);
  protected readonly repoTotal = signal(0);
  protected readonly repoOffset = signal(0);
  protected readonly repoPageSize = signal<number>(PAGE_SIZES[0]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected repoFilter = '';
  private readonly repoFilter$ = new Subject<void>();

  protected readonly selectedRepoId = signal<string | null>(null);
  // Held explicitly (not derived from the current page) so the detail panel
  // survives paging/filtering the repo list away from the selected row.
  protected readonly selectedRepo = signal<Repository | null>(null);

  protected readonly repoRangeStart = computed(() => (this.repoTotal() === 0 ? 0 : this.repoOffset() + 1));
  protected readonly repoRangeEnd = computed(() =>
    Math.min(this.repoOffset() + this.repoPageSize(), this.repoTotal()),
  );
  protected readonly repoPageCount = computed(() =>
    Math.max(1, Math.ceil(this.repoTotal() / this.repoPageSize())),
  );
  protected readonly repoCurrentPage = computed(() =>
    Math.floor(this.repoOffset() / this.repoPageSize()) + 1,
  );
  protected readonly repoCanPrev = computed(() => this.repoOffset() > 0);
  protected readonly repoCanNext = computed(() => this.repoOffset() + this.repoPageSize() < this.repoTotal());

  // --- Selected repo: tracker projects (paged + searchable) -----------------
  protected readonly projects = signal<TrackerProject[]>([]);
  protected readonly projTotal = signal(0);
  protected readonly projOffset = signal(0);
  protected readonly projPageSize = signal<number>(PAGE_SIZES[0]);
  protected readonly projLoading = signal(false);
  protected projFilter = '';
  private readonly projFilter$ = new Subject<void>();

  protected readonly projRangeStart = computed(() => (this.projTotal() === 0 ? 0 : this.projOffset() + 1));
  protected readonly projRangeEnd = computed(() =>
    Math.min(this.projOffset() + this.projPageSize(), this.projTotal()),
  );
  protected readonly projPageCount = computed(() =>
    Math.max(1, Math.ceil(this.projTotal() / this.projPageSize())),
  );
  protected readonly projCurrentPage = computed(() =>
    Math.floor(this.projOffset() / this.projPageSize()) + 1,
  );
  protected readonly projCanPrev = computed(() => this.projOffset() > 0);
  protected readonly projCanNext = computed(() => this.projOffset() + this.projPageSize() < this.projTotal());

  // --- Selected repo: grants (paged) ----------------------------------------
  protected readonly grants = signal<Grant[]>([]);
  protected readonly grantTotal = signal(0);
  protected readonly grantOffset = signal(0);
  protected readonly grantPageSize = signal<number>(PAGE_SIZES[0]);
  protected readonly grantLoading = signal(false);

  protected readonly grantRangeStart = computed(() => (this.grantTotal() === 0 ? 0 : this.grantOffset() + 1));
  protected readonly grantRangeEnd = computed(() =>
    Math.min(this.grantOffset() + this.grantPageSize(), this.grantTotal()),
  );
  protected readonly grantCanPrev = computed(() => this.grantOffset() > 0);
  protected readonly grantCanNext = computed(() => this.grantOffset() + this.grantPageSize() < this.grantTotal());

  // Add-repository form
  protected repoProvider: Provider = 'jira';
  protected repoExternalAccount = '';
  protected repoVisibility: VisibilityScope = 'org';
  protected addingRepo = signal(false);

  // Change-visibility
  protected repoNewVisibility: VisibilityScope = 'org';
  protected savingVisibility = signal(false);

  // Add-tracker-project
  protected projKey = '';
  protected projName = '';
  protected addingProject = signal(false);

  // Add-grant
  protected grantOrgId = '';
  protected grantDirection: GrantDirection = 'org';
  protected addingGrant = signal(false);

  constructor() {
    this.repoFilter$.pipe(debounceTime(300)).subscribe(() => {
      this.repoOffset.set(0);
      this.load();
    });
    this.projFilter$.pipe(debounceTime(300)).subscribe(() => {
      this.projOffset.set(0);
      this.loadProjects();
    });
    effect(() => {
      const sel = this.ctx.selected();
      untracked(() => {
        const id = sel?.org_id ?? null;
        if (id !== this.lastId) {
          this.lastId = id;
          this.selectedRepoId.set(null);
          this.selectedRepo.set(null);
          this.repoFilter = '';
          this.repoOffset.set(0);
          this.load();
        }
      });
    });
  }

  private load(): void {
    const org = this.ctx.selected();
    if (!org) {
      this.repositories.set([]);
      this.repoTotal.set(0);
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.orgAdmin
      .listRepositories(org.org_id, {
        q: this.repoFilter.trim() || undefined,
        limit: this.repoPageSize(),
        offset: this.repoOffset(),
      })
      .subscribe({
        next: (resp) => {
          this.repositories.set(resp.repositories);
          this.repoTotal.set(resp.total ?? resp.repositories.length);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Unable to load repositories.');
          this.repositories.set([]);
          this.repoTotal.set(0);
          this.loading.set(false);
        },
      });
  }

  onRepoFilterChange(): void {
    this.repoFilter$.next();
  }

  onRepoPageSizeChange(size: number): void {
    this.repoPageSize.set(Number(size));
    this.repoOffset.set(0);
    this.load();
  }

  repoPrev(): void {
    if (this.repoCanPrev()) {
      this.repoOffset.set(Math.max(0, this.repoOffset() - this.repoPageSize()));
      this.load();
    }
  }

  repoNext(): void {
    if (this.repoCanNext()) {
      this.repoOffset.set(this.repoOffset() + this.repoPageSize());
      this.load();
    }
  }

  repoJumpToPage(page: number): void {
    const target = Math.min(Math.max(1, Math.floor(page) || 1), this.repoPageCount());
    const newOffset = (target - 1) * this.repoPageSize();
    if (newOffset !== this.repoOffset()) {
      this.repoOffset.set(newOffset);
      this.load();
    }
  }

  selectRepo(repo: Repository): void {
    this.selectedRepoId.set(repo.repo_id);
    this.selectedRepo.set(repo);
    this.repoNewVisibility = repo.visibility_scope as VisibilityScope;
    this.projKey = '';
    this.projName = '';
    this.grantOrgId = '';
    this.grantDirection = 'org';
    // Load this repo's projects + grants from the paginated endpoints.
    this.projFilter = '';
    this.projOffset.set(0);
    this.grantOffset.set(0);
    this.loadProjects();
    this.loadGrants();
  }

  isRepoSelected(repo: Repository): boolean {
    return repo.repo_id === this.selectedRepoId();
  }

  // --- Selected repo: projects ----------------------------------------------

  private loadProjects(): void {
    const repoId = this.selectedRepoId();
    if (!repoId) {
      this.projects.set([]);
      this.projTotal.set(0);
      return;
    }
    this.projLoading.set(true);
    this.orgAdmin
      .listRepositoryProjects(repoId, {
        q: this.projFilter.trim() || undefined,
        limit: this.projPageSize(),
        offset: this.projOffset(),
      })
      .subscribe({
        next: (resp) => {
          this.projects.set(resp.projects);
          this.projTotal.set(resp.total ?? resp.projects.length);
          this.projLoading.set(false);
        },
        error: () => {
          this.projects.set([]);
          this.projTotal.set(0);
          this.projLoading.set(false);
        },
      });
  }

  onProjFilterChange(): void {
    this.projFilter$.next();
  }

  onProjPageSizeChange(size: number): void {
    this.projPageSize.set(Number(size));
    this.projOffset.set(0);
    this.loadProjects();
  }

  projPrev(): void {
    if (this.projCanPrev()) {
      this.projOffset.set(Math.max(0, this.projOffset() - this.projPageSize()));
      this.loadProjects();
    }
  }

  projNext(): void {
    if (this.projCanNext()) {
      this.projOffset.set(this.projOffset() + this.projPageSize());
      this.loadProjects();
    }
  }

  projJumpToPage(page: number): void {
    const target = Math.min(Math.max(1, Math.floor(page) || 1), this.projPageCount());
    const newOffset = (target - 1) * this.projPageSize();
    if (newOffset !== this.projOffset()) {
      this.projOffset.set(newOffset);
      this.loadProjects();
    }
  }

  // --- Selected repo: grants -------------------------------------------------

  private loadGrants(): void {
    const repoId = this.selectedRepoId();
    if (!repoId) {
      this.grants.set([]);
      this.grantTotal.set(0);
      return;
    }
    this.grantLoading.set(true);
    this.orgAdmin.listRepositoryGrants(repoId, this.grantPageSize(), this.grantOffset()).subscribe({
      next: (resp) => {
        this.grants.set(resp.grants);
        this.grantTotal.set(resp.total ?? resp.grants.length);
        this.grantLoading.set(false);
      },
      error: () => {
        this.grants.set([]);
        this.grantTotal.set(0);
        this.grantLoading.set(false);
      },
    });
  }

  onGrantPageSizeChange(size: number): void {
    this.grantPageSize.set(Number(size));
    this.grantOffset.set(0);
    this.loadGrants();
  }

  grantPrev(): void {
    if (this.grantCanPrev()) {
      this.grantOffset.set(Math.max(0, this.grantOffset() - this.grantPageSize()));
      this.loadGrants();
    }
  }

  grantNext(): void {
    if (this.grantCanNext()) {
      this.grantOffset.set(this.grantOffset() + this.grantPageSize());
      this.loadGrants();
    }
  }

  // --- Mutations -------------------------------------------------------------

  addRepository(): void {
    const org = this.ctx.selected();
    if (!org) {
      return;
    }
    this.addingRepo.set(true);
    const body: CreateRepositoryRequest = {
      provider: this.repoProvider,
      external_account: this.repoExternalAccount.trim() || null,
      visibility_scope: this.repoVisibility,
    };
    this.orgAdmin.createRepository(org.org_id, body).subscribe({
      next: (repo) => {
        this.addingRepo.set(false);
        this.repoExternalAccount = '';
        this.notifications.success('Repository added', `${this.providerLabels[this.repoProvider]} connected.`);
        this.repoFilter = '';
        this.repoOffset.set(0);
        this.load();
        this.selectRepo(repo);
      },
      error: (err: HttpErrorResponse) => {
        this.addingRepo.set(false);
        this.notifications.error('Add repository failed', this.errMessage(err, 'Could not add the repository.'));
      },
    });
  }

  async changeVisibility(): Promise<void> {
    const repo = this.selectedRepo();
    if (!repo || this.repoNewVisibility === repo.visibility_scope) {
      return;
    }
    const ok = await this.notifications.confirm({
      title: 'Change repository visibility?',
      message: `Set visibility of this repository to "${this.repoNewVisibility}" — ${this.visibilityHints[this.repoNewVisibility]}.`,
      confirmLabel: 'Apply',
    });
    if (!ok) {
      return;
    }
    this.savingVisibility.set(true);
    this.orgAdmin.setVisibility(repo.repo_id, { visibility_scope: this.repoNewVisibility }).subscribe({
      next: (updated) => {
        this.savingVisibility.set(false);
        this.selectedRepo.set(updated); // keep the detail panel's scope in sync
        this.notifications.success('Visibility updated', `Now "${this.repoNewVisibility}".`);
        this.load();
      },
      error: (err: HttpErrorResponse) => {
        this.savingVisibility.set(false);
        this.notifications.error('Update failed', this.errMessage(err, 'Could not change visibility.'));
      },
    });
  }

  addProject(): void {
    const repo = this.selectedRepo();
    const key = this.projKey.trim();
    if (!repo || !key) {
      return;
    }
    this.addingProject.set(true);
    const body: AddTrackerProjectsRequest = {
      projects: [{ external_key: key, name: this.projName.trim() || null }],
    };
    this.orgAdmin.addTrackerProjects(repo.repo_id, body).subscribe({
      next: (resp) => {
        this.addingProject.set(false);
        this.projKey = '';
        this.projName = '';
        this.notifications.success('Tracker project added', `${resp.projects.length} project(s) upserted.`);
        // Reload the (server-paged) list from the top so the new row shows.
        this.projFilter = '';
        this.projOffset.set(0);
        this.loadProjects();
      },
      error: (err: HttpErrorResponse) => {
        this.addingProject.set(false);
        this.notifications.error('Add project failed', this.errMessage(err, 'Could not add the tracker project.'));
      },
    });
  }

  addGrant(): void {
    const repo = this.selectedRepo();
    const grantee = this.grantOrgId.trim();
    if (!repo || !grantee) {
      return;
    }
    this.addingGrant.set(true);
    const body: AddGrantRequest = { grantee_org_id: grantee, direction: this.grantDirection };
    this.orgAdmin.addGrant(repo.repo_id, body).subscribe({
      next: (grant) => {
        this.addingGrant.set(false);
        this.grantOrgId = '';
        this.notifications.success('Grant added', `Shared with ${grant.grantee_org_id} (${grant.direction}).`);
        this.grantOffset.set(0);
        this.loadGrants();
      },
      error: (err: HttpErrorResponse) => {
        this.addingGrant.set(false);
        this.notifications.error('Add grant failed', this.errMessage(err, 'Could not add the grant.'));
      },
    });
  }

  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    return body?.error?.message ?? fallback;
  }
}
