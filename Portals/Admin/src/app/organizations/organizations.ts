import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';

import {
  AddGrantRequest,
  AddMemberRequest,
  AddTrackerProjectsRequest,
  CreateOrganizationRequest,
  CreateRepositoryRequest,
  GRANT_DIRECTIONS,
  Grant,
  GrantDirection,
  Member,
  Organization,
  PROVIDER_LABELS,
  PROVIDERS,
  Provider,
  ROLE_OPTIONS,
  Repository,
  TrackerProject,
  VISIBILITY_HINTS,
  VISIBILITY_SCOPES,
  VisibilityScope,
  VisibleProject,
} from '../models/org';
import { OrgAdminService } from '../services/org-admin.service';
import { NotificationService } from '../ui/notification.service';

/** An org node decorated with tree-render metadata (flattened DFS order). */
interface OrgNode extends Organization {
  /** Indentation depth for rendering (== depth field, root = 0). */
  indent: number;
}

@Component({
  selector: 'app-organizations',
  imports: [FormsModule],
  templateUrl: './organizations.html',
  styleUrl: './organizations.css',
})
export class Organizations implements OnInit {
  private readonly orgAdmin = inject(OrgAdminService);
  private readonly notifications = inject(NotificationService);

  // Static option lists (bound to dropdowns / multi-selects).
  protected readonly providers = PROVIDERS;
  protected readonly providerLabels = PROVIDER_LABELS;
  protected readonly visibilityScopes = VISIBILITY_SCOPES;
  protected readonly visibilityHints = VISIBILITY_HINTS;
  protected readonly grantDirections = GRANT_DIRECTIONS;
  protected readonly roleOptions = ROLE_OPTIONS;

  // --- Org tree -------------------------------------------------------------
  protected readonly orgs = signal<Organization[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly selectedOrgId = signal<string | null>(null);

  /** Flattened, DFS-ordered tree (sorting by materialized path == DFS order). */
  protected readonly tree = computed<OrgNode[]>(() =>
    [...this.orgs()]
      .sort((a, b) => a.path.localeCompare(b.path))
      .map((o) => ({ ...o, indent: o.depth })),
  );

  protected readonly selectedOrg = computed<Organization | null>(
    () => this.orgs().find((o) => o.org_id === this.selectedOrgId()) ?? null,
  );

  // KPIs
  protected readonly rootCount = computed(
    () => this.orgs().filter((o) => o.parent_org_id == null).length,
  );
  protected readonly maxLevel = computed(() =>
    this.orgs().reduce((m, o) => Math.max(m, o.level), 0),
  );

  // Create-root form
  protected rootName = '';
  protected rootKind = '';
  protected creatingRoot = signal(false);

  // Create-child form (uses the selected org as parent)
  protected childName = '';
  protected childKind = '';
  protected creatingChild = signal(false);

  // Rename form
  protected renameName = '';
  protected renameKind = '';
  protected renaming = signal(false);

  // Move form
  protected moveTargetId = '';
  protected moving = signal(false);

  // --- Members --------------------------------------------------------------
  protected readonly members = signal<Member[]>([]);
  protected readonly membersLoading = signal(false);
  protected readonly membersError = signal<string | null>(null);

  protected memberSubject = '';
  protected memberRoles: string[] = [];
  protected memberInherits = true;
  protected addingMember = signal(false);

  // --- Repositories ---------------------------------------------------------
  protected readonly repositories = signal<Repository[]>([]);
  protected readonly reposLoading = signal(false);
  protected readonly reposError = signal<string | null>(null);
  protected readonly selectedRepoId = signal<string | null>(null);

  /** Tracker projects added this session, keyed by repo (no list-projects API). */
  protected readonly repoProjects = signal<Record<string, TrackerProject[]>>({});
  /** Grants added this session, keyed by repo (no list-grants API). */
  protected readonly repoGrants = signal<Record<string, Grant[]>>({});

  protected readonly selectedRepo = computed<Repository | null>(
    () => this.repositories().find((r) => r.repo_id === this.selectedRepoId()) ?? null,
  );

  // Add-repository form
  protected repoProvider: Provider = 'jira';
  protected repoExternalAccount = '';
  protected repoVisibility: VisibilityScope = 'org';
  protected addingRepo = signal(false);

  // Change-visibility (for the selected repo)
  protected repoNewVisibility: VisibilityScope = 'org';
  protected savingVisibility = signal(false);

  // Add-tracker-project form (for the selected repo)
  protected projKey = '';
  protected projName = '';
  protected addingProject = signal(false);

  // Add-grant form (for the selected repo)
  protected grantOrgId = '';
  protected grantDirection: GrantDirection = 'org';
  protected addingGrant = signal(false);

  // --- Effective-access preview --------------------------------------------
  protected accessSubject = '';
  protected readonly accessProjects = signal<VisibleProject[] | null>(null);
  protected readonly accessLoading = signal(false);
  protected readonly accessError = signal<string | null>(null);
  protected readonly accessResolvedSubject = signal<string | null>(null);

  ngOnInit(): void {
    this.loadTree();
  }

  // ==========================================================================
  // Org tree
  // ==========================================================================

  loadTree(): void {
    this.loading.set(true);
    this.error.set(null);
    this.orgAdmin.listRoots().subscribe({
      next: (roots) => {
        const rootOrgs = roots.organizations;
        if (rootOrgs.length === 0) {
          this.orgs.set([]);
          this.loading.set(false);
          return;
        }
        // Each root's subtree includes the root + all descendants; merge + dedupe.
        forkJoin(rootOrgs.map((r) => this.orgAdmin.subtree(r.org_id))).subscribe({
          next: (subtrees) => {
            const byId = new Map<string, Organization>();
            for (const st of subtrees) {
              for (const o of st.organizations) {
                byId.set(o.org_id, o);
              }
            }
            this.orgs.set([...byId.values()]);
            this.loading.set(false);
            // Keep or clear the current selection depending on whether it survives.
            const sel = this.selectedOrgId();
            if (sel && byId.has(sel)) {
              this.selectOrg(byId.get(sel)!, false);
            } else {
              this.selectedOrgId.set(null);
            }
          },
          error: () => this.failTree(),
        });
      },
      error: () => this.failTree(),
    });
  }

  private failTree(): void {
    this.error.set('Unable to load organizations. Is the Org-Management-API running on :8005?');
    this.orgs.set([]);
    this.loading.set(false);
  }

  isSelected(org: Organization): boolean {
    return org.org_id === this.selectedOrgId();
  }

  /** Select a node and (re)load its members + repositories. */
  selectOrg(org: Organization, resetForms = true): void {
    this.selectedOrgId.set(org.org_id);
    if (resetForms) {
      this.renameName = org.name;
      this.renameKind = org.kind ?? '';
      this.childName = '';
      this.childKind = '';
      this.moveTargetId = '';
      this.memberSubject = '';
      this.memberRoles = [];
      this.memberInherits = true;
      this.repoExternalAccount = '';
      this.selectedRepoId.set(null);
    }
    this.loadMembers(org.org_id);
    this.loadRepositories(org.org_id);
  }

  createRoot(): void {
    const name = this.rootName.trim();
    if (!name) {
      return;
    }
    this.creatingRoot.set(true);
    const body: CreateOrganizationRequest = {
      name,
      kind: this.rootKind.trim() || null,
    };
    this.orgAdmin.createOrg(body).subscribe({
      next: (org) => {
        this.creatingRoot.set(false);
        this.rootName = '';
        this.rootKind = '';
        this.notifications.success('Root organization created', `${org.name} (level ${org.level}).`);
        this.selectedOrgId.set(org.org_id);
        this.loadTree();
      },
      error: (err: HttpErrorResponse) => {
        this.creatingRoot.set(false);
        this.notifications.error('Create failed', this.errMessage(err, 'Could not create the root organization.'));
      },
    });
  }

  async createChild(): Promise<void> {
    const parent = this.selectedOrg();
    const name = this.childName.trim();
    if (!parent || !name) {
      return;
    }
    const ok = await this.notifications.confirm({
      title: 'Create child organization?',
      message: `Create "${name}" under "${parent.name}" (level ${parent.level + 1}).`,
      confirmLabel: 'Create child',
    });
    if (!ok) {
      return;
    }
    this.creatingChild.set(true);
    const body: CreateOrganizationRequest = {
      name,
      parent_org_id: parent.org_id,
      kind: this.childKind.trim() || null,
    };
    this.orgAdmin.createOrg(body).subscribe({
      next: (org) => {
        this.creatingChild.set(false);
        this.childName = '';
        this.childKind = '';
        this.notifications.success('Child organization created', `${org.name} added under ${parent.name}.`);
        this.selectedOrgId.set(org.org_id);
        this.loadTree();
      },
      error: (err: HttpErrorResponse) => {
        this.creatingChild.set(false);
        this.notifications.error('Create failed', this.errMessage(err, 'Could not create the child organization.'));
      },
    });
  }

  async rename(): Promise<void> {
    const org = this.selectedOrg();
    const name = this.renameName.trim();
    if (!org || !name) {
      return;
    }
    const kind = this.renameKind.trim() || null;
    if (name === org.name && kind === (org.kind ?? null)) {
      return;
    }
    const ok = await this.notifications.confirm({
      title: 'Rename organization?',
      message: `Rename "${org.name}" to "${name}"${kind ? ` (kind: ${kind})` : ''}.`,
      confirmLabel: 'Save',
    });
    if (!ok) {
      return;
    }
    this.renaming.set(true);
    this.orgAdmin.updateOrg(org.org_id, { name, kind }).subscribe({
      next: (updated) => {
        this.renaming.set(false);
        this.notifications.success('Organization updated', `Now "${updated.name}".`);
        this.loadTree();
      },
      error: (err: HttpErrorResponse) => {
        this.renaming.set(false);
        this.notifications.error('Update failed', this.errMessage(err, 'Could not rename the organization.'));
      },
    });
  }

  async move(): Promise<void> {
    const org = this.selectedOrg();
    const target = this.moveTargetId.trim();
    if (!org || !target) {
      return;
    }
    const ok = await this.notifications.confirm({
      title: 'Move organization?',
      message: `Reparent "${org.name}" (and its whole subtree) under org ${target}. Moving a node beneath itself is rejected.`,
      confirmLabel: 'Move',
      danger: true,
    });
    if (!ok) {
      return;
    }
    this.moving.set(true);
    this.orgAdmin.moveOrg(org.org_id, { new_parent_org_id: target }).subscribe({
      next: (updated) => {
        this.moving.set(false);
        this.moveTargetId = '';
        this.notifications.success('Organization moved', `"${updated.name}" is now at level ${updated.level}.`);
        this.loadTree();
      },
      error: (err: HttpErrorResponse) => {
        this.moving.set(false);
        // The cycle guard surfaces here as a domain error message.
        this.notifications.error('Move rejected', this.errMessage(err, 'Could not move the organization.'));
      },
    });
  }

  // ==========================================================================
  // Members
  // ==========================================================================

  loadMembers(orgId: string): void {
    this.membersLoading.set(true);
    this.membersError.set(null);
    this.orgAdmin.listMembers(orgId).subscribe({
      next: (resp) => {
        this.members.set(resp.members);
        this.membersLoading.set(false);
      },
      error: () => {
        this.membersError.set('Unable to load members.');
        this.members.set([]);
        this.membersLoading.set(false);
      },
    });
  }

  addMember(): void {
    const org = this.selectedOrg();
    const subject = this.memberSubject.trim();
    if (!org || !subject) {
      return;
    }
    this.addingMember.set(true);
    const body: AddMemberRequest = {
      subject,
      roles: [...this.memberRoles],
      inherits_down: this.memberInherits,
    };
    this.orgAdmin.addMember(org.org_id, body).subscribe({
      next: (member) => {
        this.addingMember.set(false);
        this.memberSubject = '';
        this.memberRoles = [];
        this.memberInherits = true;
        this.notifications.success('Member added', `${member.subject} added to ${org.name}.`);
        this.loadMembers(org.org_id);
      },
      error: (err: HttpErrorResponse) => {
        this.addingMember.set(false);
        this.notifications.error('Add member failed', this.errMessage(err, 'Could not add the member.'));
      },
    });
  }

  roleNames(member: Member): string {
    return member.roles.map((r) => r.role).join(', ') || '—';
  }

  // ==========================================================================
  // Repositories
  // ==========================================================================

  loadRepositories(orgId: string): void {
    this.reposLoading.set(true);
    this.reposError.set(null);
    this.orgAdmin.listRepositories(orgId).subscribe({
      next: (resp) => {
        this.repositories.set(resp.repositories);
        this.reposLoading.set(false);
      },
      error: () => {
        this.reposError.set('Unable to load repositories.');
        this.repositories.set([]);
        this.reposLoading.set(false);
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
    const org = this.selectedOrg();
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
        this.notifications.success('Repository added', `${this.providerLabels[this.repoProvider]} connected to ${org.name}.`);
        this.loadRepositories(org.org_id);
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
        const org = this.selectedOrg();
        if (org) {
          this.loadRepositories(org.org_id);
        }
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

  // ==========================================================================
  // Effective-access preview
  // ==========================================================================

  resolveAccess(): void {
    const subject = this.accessSubject.trim();
    if (!subject) {
      return;
    }
    this.accessLoading.set(true);
    this.accessError.set(null);
    this.accessProjects.set(null);
    this.orgAdmin.visibleProjects(subject).subscribe({
      next: (resp) => {
        this.accessLoading.set(false);
        this.accessProjects.set(resp.projects);
        this.accessResolvedSubject.set(resp.subject);
      },
      error: (err: HttpErrorResponse) => {
        this.accessLoading.set(false);
        this.accessProjects.set(null);
        this.accessError.set(this.errMessage(err, 'Unable to resolve visible projects. Is the Org-Management-API running on :8005?'));
      },
    });
  }

  // ==========================================================================
  // Helpers
  // ==========================================================================

  /** Pull the domain error message out of the standard error envelope. */
  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    if (body?.error?.message) {
      return body.error.message;
    }
    return fallback;
  }
}
