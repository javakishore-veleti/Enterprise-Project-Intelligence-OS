import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { CreateOrganizationRequest, Organization } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';
import { NotificationService } from '../../ui/notification.service';
import { OrgPicker } from '../org-picker/org-picker';

/** Children fetched per page (paginated `children` endpoint). */
const CHILD_PAGE = 25;

/**
 * Sub-Organizations page (route: /organizations/sub-orgs) — the hierarchy
 * navigator. Shows the selected org's DIRECT children from the paginated
 * `children` endpoint (lazy, "load more"), lets you create a child, search the
 * tenant, and DRILL IN: clicking a child makes it the selected org (shared
 * context) so you can descend the tree any number of levels; an "up to parent"
 * control ascends. Never loads a whole subtree.
 */
@Component({
  selector: 'app-org-sub-orgs',
  imports: [FormsModule, OrgPicker],
  templateUrl: './org-sub-orgs.html',
  styleUrls: ['../org.css'],
})
export class OrgSubOrgs {
  private readonly orgAdmin = inject(OrgAdminService);
  protected readonly ctx = inject(OrgContextService);
  private readonly notifications = inject(NotificationService);

  protected readonly children = signal<Organization[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  private lastId: string | null = null;

  protected childName = '';
  protected childKind = '';
  protected creatingChild = signal(false);

  // Tenant search (jump anywhere under the same root)
  protected searchQuery = '';
  protected readonly searching = signal(false);
  protected readonly searchLoading = signal(false);
  protected readonly searchResults = signal<Organization[]>([]);
  private readonly input$ = new Subject<string>();

  constructor() {
    this.input$.pipe(debounceTime(300)).subscribe((q) => this.runSearch(q));
    effect(() => {
      const sel = this.ctx.selected();
      untracked(() => {
        const id = sel?.org_id ?? null;
        if (id !== this.lastId) {
          this.lastId = id;
          this.clearSearch();
          this.loadChildren(0);
        }
      });
    });
  }

  private loadChildren(offset: number): void {
    const org = this.ctx.selected();
    if (!org) {
      this.children.set([]);
      this.total.set(0);
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.orgAdmin.children(org.org_id, CHILD_PAGE, offset).subscribe({
      next: (resp) => {
        const existing = offset === 0 ? [] : this.children();
        this.children.set([...existing, ...resp.organizations]);
        this.total.set(resp.total ?? resp.organizations.length);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load sub-organizations.');
        if (offset === 0) {
          this.children.set([]);
          this.total.set(0);
        }
        this.loading.set(false);
      },
    });
  }

  loadMore(): void {
    this.loadChildren(this.children().length);
  }

  get remaining(): number {
    return this.total() - this.children().length;
  }

  /** Drill INTO a child (make it the selected org). */
  drillIn(child: Organization): void {
    this.ctx.select(child);
  }

  /** Ascend to the parent of the selected org, if any. */
  goUp(): void {
    const org = this.ctx.selected();
    if (!org?.parent_org_id) {
      return;
    }
    this.orgAdmin.getOrg(org.parent_org_id).subscribe({
      next: (parent) => this.ctx.select(parent),
      error: () => this.notifications.error('Navigation failed', 'Could not load the parent organization.'),
    });
  }

  createChild(): void {
    const parent = this.ctx.selected();
    const name = this.childName.trim();
    if (!parent || !name) {
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
        this.loadChildren(0);
        this.refreshSelectedCounts();
      },
      error: (err: HttpErrorResponse) => {
        this.creatingChild.set(false);
        this.notifications.error('Create failed', this.errMessage(err, 'Could not create the child organization.'));
      },
    });
  }

  /** Refresh the selected org's counts in context (same id ⇒ no child reload). */
  private refreshSelectedCounts(): void {
    const org = this.ctx.selected();
    if (org) {
      this.orgAdmin.getOrg(org.org_id).subscribe({ next: (o) => this.ctx.select(o), error: () => {} });
    }
  }

  onSearchChange(value: string): void {
    this.input$.next(value);
  }

  private runSearch(q: string): void {
    const term = q.trim();
    const org = this.ctx.selected();
    if (!term || !org) {
      this.searching.set(false);
      this.searchResults.set([]);
      return;
    }
    this.searching.set(true);
    this.searchLoading.set(true);
    // Scope to the current tenant so results stay within this hierarchy.
    this.orgAdmin.searchOrgs(term, org.root_org_id, 25, 0).subscribe({
      next: (resp) => {
        this.searchResults.set(resp.organizations);
        this.searchLoading.set(false);
      },
      error: () => {
        this.searchResults.set([]);
        this.searchLoading.set(false);
      },
    });
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.searching.set(false);
    this.searchResults.set([]);
  }

  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    return body?.error?.message ?? fallback;
  }
}
