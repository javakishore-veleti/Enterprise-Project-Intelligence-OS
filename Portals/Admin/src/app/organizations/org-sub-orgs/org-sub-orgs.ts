import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import {
  CreateOrganizationRequest,
  OrgChildSort,
  Organization,
} from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';
import { NotificationService } from '../../ui/notification.service';
import { OrgPicker } from '../org-picker/org-picker';

/** Page sizes offered by the selector — bounded regardless of total. */
const PAGE_SIZES = [25, 50, 100] as const;

/**
 * Sub-Organizations page (route: /organizations/sub-orgs) — the hierarchy
 * navigator, built to scale to an org with 500–10,000 DIRECT children.
 *
 * Only the CURRENT page of children is rendered (page-replacement, ~25 rows by
 * default) — Prev/Next/jump refetch that page from the paginated `children`
 * endpoint, so the DOM never grows with the total. A debounced filter (`q`) and
 * a sort (name / newest / most sub-orgs) run server-side and reset to page 0.
 * DRILL IN: clicking a child makes it the selected org (shared context) so you
 * can descend the tree any number of levels; "up to parent" ascends. Never
 * loads a whole subtree.
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
  private readonly router = inject(Router);

  protected readonly pageSizes = PAGE_SIZES;

  // Current page of direct children (replaced per page — never accumulated).
  protected readonly children = signal<Organization[]>([]);
  protected readonly total = signal(0);
  protected readonly offset = signal(0);
  protected readonly pageSize = signal<number>(PAGE_SIZES[0]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  private lastId: string | null = null;

  // In-list filter (scoped to THIS org's children) + sort.
  protected filter = '';
  protected sortBy: OrgChildSort = 'name';
  private readonly filter$ = new Subject<void>();

  // Paging display helpers.
  protected readonly rangeStart = computed(() => (this.total() === 0 ? 0 : this.offset() + 1));
  protected readonly rangeEnd = computed(() =>
    Math.min(this.offset() + this.pageSize(), this.total()),
  );
  protected readonly pageCount = computed(() =>
    Math.max(1, Math.ceil(this.total() / this.pageSize())),
  );
  protected readonly currentPage = computed(() =>
    Math.floor(this.offset() / this.pageSize()) + 1,
  );
  protected readonly canPrev = computed(() => this.offset() > 0);
  protected readonly canNext = computed(() => this.offset() + this.pageSize() < this.total());

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
    this.filter$.pipe(debounceTime(300)).subscribe(() => {
      this.offset.set(0);
      this.load();
    });
    effect(() => {
      const sel = this.ctx.selected();
      untracked(() => {
        const id = sel?.org_id ?? null;
        if (id !== this.lastId) {
          this.lastId = id;
          this.clearSearch();
          this.filter = '';
          this.sortBy = 'name';
          this.offset.set(0);
          this.load();
        }
      });
    });
  }

  private load(): void {
    const org = this.ctx.selected();
    if (!org) {
      this.children.set([]);
      this.total.set(0);
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.orgAdmin
      .children(org.org_id, {
        q: this.filter.trim() || undefined,
        sort: this.sortBy,
        limit: this.pageSize(),
        offset: this.offset(),
      })
      .subscribe({
        next: (resp) => {
          this.children.set(resp.organizations);
          this.total.set(resp.total ?? resp.organizations.length);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Unable to load sub-organizations.');
          this.children.set([]);
          this.total.set(0);
          this.loading.set(false);
        },
      });
  }

  onFilterChange(): void {
    this.filter$.next();
  }

  onSortChange(): void {
    this.offset.set(0);
    this.load();
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(Number(size));
    this.offset.set(0);
    this.load();
  }

  prev(): void {
    if (this.canPrev()) {
      this.offset.set(Math.max(0, this.offset() - this.pageSize()));
      this.load();
    }
  }

  next(): void {
    if (this.canNext()) {
      this.offset.set(this.offset() + this.pageSize());
      this.load();
    }
  }

  jumpToPage(page: number): void {
    const target = Math.min(Math.max(1, Math.floor(page) || 1), this.pageCount());
    const newOffset = (target - 1) * this.pageSize();
    if (newOffset !== this.offset()) {
      this.offset.set(newOffset);
      this.load();
    }
  }

  /** Drill INTO a child (make it the selected org — its children then load). */
  drillIn(child: Organization): void {
    this.ctx.select(child);
  }

  /** Select a child and open its full profile page. */
  openProfile(child: Organization): void {
    this.ctx.select(child);
    this.router.navigate(['/organizations/profile']);
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
        this.offset.set(0);
        this.load();
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
