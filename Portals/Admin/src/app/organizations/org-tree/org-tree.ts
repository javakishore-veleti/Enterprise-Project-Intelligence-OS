import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { CreateOrganizationRequest, Organization } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { NotificationService } from '../../ui/notification.service';

/** How many children to fetch per page when a node is expanded. */
const CHILD_PAGE = 25;

/** One rendered row of the lazy tree (flattened DFS). */
interface TreeRow {
  org: Organization;
  expanded: boolean;
  loading: boolean;
  hasMore: boolean;
  remaining: number;
}

/**
 * The Organization Tree page (route: /organizations). Loads ONLY roots, then
 * fetches a node's children on demand (paged) when it is expanded — it never
 * loads a whole subtree. A debounced search box queries the server and lets the
 * operator jump straight to any org.
 */
@Component({
  selector: 'app-org-tree',
  imports: [FormsModule],
  templateUrl: './org-tree.html',
  styleUrls: ['../org.css', './org-tree.css'],
})
export class OrgTree implements OnInit {
  private readonly orgAdmin = inject(OrgAdminService);
  private readonly notifications = inject(NotificationService);
  private readonly router = inject(Router);

  // --- Roots + lazy child state --------------------------------------------
  protected readonly roots = signal<Organization[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  /** org_id -> loaded children (a prefix of all children, grown by "load more"). */
  private readonly childrenMap = signal<Record<string, Organization[]>>({});
  /** org_id -> total child count reported by the server. */
  private readonly childTotal = signal<Record<string, number>>({});
  private readonly expanded = signal<Set<string>>(new Set());
  private readonly loadingNodes = signal<Set<string>>(new Set());

  /** Flattened, DFS-ordered rows built from roots + expanded + loaded children. */
  protected readonly rows = computed<TreeRow[]>(() => this.buildRows());

  // --- Search --------------------------------------------------------------
  protected searchQuery = '';
  protected searchRoot = ''; // '' = all tenants
  protected readonly searching = signal(false);
  protected readonly searchLoading = signal(false);
  protected readonly searchResults = signal<Organization[]>([]);
  protected readonly searchTotal = signal(0);
  private readonly searchInput$ = new Subject<string>();

  // --- Create root form ----------------------------------------------------
  protected rootName = '';
  protected rootKind = '';
  protected creatingRoot = signal(false);

  ngOnInit(): void {
    this.searchInput$.pipe(debounceTime(300)).subscribe((q) => this.runSearch(q));
    this.loadRoots();
  }

  // ==========================================================================
  // Roots + lazy children
  // ==========================================================================

  loadRoots(): void {
    this.loading.set(true);
    this.error.set(null);
    this.orgAdmin.listRoots().subscribe({
      next: (resp) => {
        this.roots.set(resp.organizations);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load organizations. Is the Org-Management-API running on :8005?');
        this.roots.set([]);
        this.loading.set(false);
      },
    });
  }

  private buildRows(): TreeRow[] {
    const out: TreeRow[] = [];
    const expanded = this.expanded();
    const loaded = this.childrenMap();
    const totals = this.childTotal();
    const busy = this.loadingNodes();

    const walk = (nodes: Organization[]): void => {
      for (const o of nodes) {
        const isOpen = expanded.has(o.org_id);
        const kids = loaded[o.org_id];
        const total = totals[o.org_id] ?? o.child_count ?? 0;
        out.push({
          org: o,
          expanded: isOpen,
          loading: busy.has(o.org_id),
          hasMore: isOpen && kids != null && kids.length < total,
          remaining: total - (kids?.length ?? 0),
        });
        if (isOpen && kids) {
          walk(kids);
        }
      }
    };
    walk(this.roots());
    return out;
  }

  hasChildren(o: Organization): boolean {
    return (o.child_count ?? 0) > 0;
  }

  indentPx(o: Organization): number {
    return 6 + o.depth * 20;
  }

  toggle(o: Organization): void {
    const next = new Set(this.expanded());
    if (next.has(o.org_id)) {
      next.delete(o.org_id);
      this.expanded.set(next);
      return;
    }
    next.add(o.org_id);
    this.expanded.set(next);
    if (this.childrenMap()[o.org_id] == null) {
      this.loadChildren(o.org_id, 0);
    }
  }

  /** Fetch a page of children; offset 0 replaces, otherwise appends. */
  private loadChildren(orgId: string, offset: number): void {
    this.setLoadingNode(orgId, true);
    this.orgAdmin.children(orgId, CHILD_PAGE, offset).subscribe({
      next: (resp) => {
        this.childrenMap.update((m) => {
          const existing = offset === 0 ? [] : m[orgId] ?? [];
          return { ...m, [orgId]: [...existing, ...resp.organizations] };
        });
        this.childTotal.update((t) => ({ ...t, [orgId]: resp.total ?? resp.organizations.length }));
        this.setLoadingNode(orgId, false);
      },
      error: () => {
        this.setLoadingNode(orgId, false);
        this.notifications.error('Load failed', 'Could not load child organizations.');
      },
    });
  }

  loadMore(orgId: string): void {
    const loaded = this.childrenMap()[orgId]?.length ?? 0;
    this.loadChildren(orgId, loaded);
  }

  private setLoadingNode(orgId: string, on: boolean): void {
    const next = new Set(this.loadingNodes());
    if (on) {
      next.add(orgId);
    } else {
      next.delete(orgId);
    }
    this.loadingNodes.set(next);
  }

  open(org: Organization): void {
    this.router.navigate(['/organizations', org.org_id]);
  }

  // ==========================================================================
  // Search
  // ==========================================================================

  onSearchChange(value: string): void {
    this.searchInput$.next(value);
  }

  private runSearch(q: string): void {
    const term = q.trim();
    if (!term) {
      this.searching.set(false);
      this.searchResults.set([]);
      this.searchTotal.set(0);
      return;
    }
    this.searching.set(true);
    this.searchLoading.set(true);
    this.orgAdmin.searchOrgs(term, this.searchRoot || null, 25, 0).subscribe({
      next: (resp) => {
        this.searchResults.set(resp.organizations);
        this.searchTotal.set(resp.total ?? resp.organizations.length);
        this.searchLoading.set(false);
      },
      error: () => {
        this.searchResults.set([]);
        this.searchTotal.set(0);
        this.searchLoading.set(false);
      },
    });
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.searching.set(false);
    this.searchResults.set([]);
    this.searchTotal.set(0);
  }

  onScopeChange(): void {
    if (this.searchQuery.trim()) {
      this.runSearch(this.searchQuery);
    }
  }

  // ==========================================================================
  // Create root
  // ==========================================================================

  createRoot(): void {
    const name = this.rootName.trim();
    if (!name) {
      return;
    }
    this.creatingRoot.set(true);
    const body: CreateOrganizationRequest = { name, kind: this.rootKind.trim() || null };
    this.orgAdmin.createOrg(body).subscribe({
      next: (org) => {
        this.creatingRoot.set(false);
        this.rootName = '';
        this.rootKind = '';
        this.notifications.success('Root organization created', `${org.name} (level ${org.level}).`);
        this.loadRoots();
      },
      error: (err: HttpErrorResponse) => {
        this.creatingRoot.set(false);
        this.notifications.error('Create failed', this.errMessage(err, 'Could not create the root organization.'));
      },
    });
  }

  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    return body?.error?.message ?? fallback;
  }
}
