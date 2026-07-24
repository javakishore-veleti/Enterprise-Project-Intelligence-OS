import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

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
import { NotificationService } from '../../ui/notification.service';

/**
 * Repositories & Visibility page (route: /organizations/:orgId/repositories).
 * Lists / adds repos for this org, sets visibility scope, adds tracker projects
 * and cross-org grants. Loads only this org's repositories.
 */
@Component({
  selector: 'app-org-repositories',
  imports: [FormsModule],
  templateUrl: './org-repositories.html',
  styleUrls: ['../org.css'],
})
export class OrgRepositories implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly orgAdmin = inject(OrgAdminService);
  private readonly notifications = inject(NotificationService);

  protected readonly providers = PROVIDERS;
  protected readonly providerLabels = PROVIDER_LABELS;
  protected readonly visibilityScopes = VISIBILITY_SCOPES;
  protected readonly visibilityHints = VISIBILITY_HINTS;
  protected readonly grantDirections = GRANT_DIRECTIONS;

  protected readonly orgId = signal<string>('');
  protected readonly repositories = signal<Repository[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly selectedRepoId = signal<string | null>(null);

  protected readonly repoProjects = signal<Record<string, TrackerProject[]>>({});
  protected readonly repoGrants = signal<Record<string, Grant[]>>({});

  protected readonly selectedRepo = computed<Repository | null>(
    () => this.repositories().find((r) => r.repo_id === this.selectedRepoId()) ?? null,
  );

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

  ngOnInit(): void {
    this.route.paramMap.subscribe((pm) => {
      this.orgId.set(pm.get('orgId') ?? '');
      this.selectedRepoId.set(null);
      this.load();
    });
  }

  private load(): void {
    const id = this.orgId();
    if (!id) {
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.orgAdmin.listRepositories(id).subscribe({
      next: (resp) => {
        this.repositories.set(resp.repositories);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load repositories.');
        this.repositories.set([]);
        this.loading.set(false);
      },
    });
  }

  selectRepo(repo: Repository): void {
    this.selectedRepoId.set(repo.repo_id);
    this.repoNewVisibility = repo.visibility_scope as VisibilityScope;
    this.projKey = '';
    this.projName = '';
    this.grantOrgId = '';
    this.grantDirection = 'org';
  }

  isRepoSelected(repo: Repository): boolean {
    return repo.repo_id === this.selectedRepoId();
  }

  addRepository(): void {
    const id = this.orgId();
    if (!id) {
      return;
    }
    this.addingRepo.set(true);
    const body: CreateRepositoryRequest = {
      provider: this.repoProvider,
      external_account: this.repoExternalAccount.trim() || null,
      visibility_scope: this.repoVisibility,
    };
    this.orgAdmin.createRepository(id, body).subscribe({
      next: (repo) => {
        this.addingRepo.set(false);
        this.repoExternalAccount = '';
        this.notifications.success('Repository added', `${this.providerLabels[this.repoProvider]} connected.`);
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
      next: () => {
        this.savingVisibility.set(false);
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
        this.repoProjects.update((m) => ({ ...m, [repo.repo_id]: resp.projects }));
        this.notifications.success('Tracker project added', `${resp.projects.length} project(s) on this repository.`);
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
        this.repoGrants.update((m) => ({
          ...m,
          [repo.repo_id]: [...(m[repo.repo_id] ?? []), grant],
        }));
        this.notifications.success('Grant added', `Shared with ${grant.grantee_org_id} (${grant.direction}).`);
      },
      error: (err: HttpErrorResponse) => {
        this.addingGrant.set(false);
        this.notifications.error('Add grant failed', this.errMessage(err, 'Could not add the grant.'));
      },
    });
  }

  projectsFor(repoId: string): TrackerProject[] {
    return this.repoProjects()[repoId] ?? [];
  }

  grantsFor(repoId: string): Grant[] {
    return this.repoGrants()[repoId] ?? [];
  }

  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    return body?.error?.message ?? fallback;
  }
}
