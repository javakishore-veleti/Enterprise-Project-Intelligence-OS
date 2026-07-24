import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { AuditEvent } from '../models/admin';
import { AdminService } from '../services/admin.service';

/** Page sizes offered by the selector — bounded regardless of total. */
const PAGE_SIZES = [25, 50, 100] as const;

/**
 * Audit page — server-paged + searchable, built to scale to a large audit log.
 *
 * Only the CURRENT page of events is rendered (page-replacement, ~25 rows by
 * default), so the DOM never grows with the total. A debounced search (`q`,
 * matched server-side on action / actor / entity_key / entity_type) and
 * Prev/Next refetch a fresh page from the paginated `GET /admin/audit`
 * endpoint. The total comes from the endpoint's cheap COUNT — never by
 * fetching every row to count.
 */
@Component({
  selector: 'app-audit-list',
  imports: [FormsModule],
  templateUrl: './audit-list.html',
  // Reuse the shared org pager / form-row / field styles (as the org pages do)
  // alongside the audit-specific styles, so the bounded pager + search look
  // consistent with the rest of the console.
  styleUrls: ['./audit-list.css', '../organizations/org.css'],
})
export class AuditList implements OnInit {
  private readonly adminService = inject(AdminService);

  protected readonly pageSizes = PAGE_SIZES;

  // Current page of events (replaced per page — never accumulated).
  protected readonly events = signal<AuditEvent[]>([]);
  protected readonly total = signal(0);
  protected readonly offset = signal(0);
  protected readonly pageSize = signal<number>(PAGE_SIZES[0]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  // Search (server-side, debounced; resets to page 0).
  protected query = '';
  private readonly search$ = new Subject<void>();

  // KPIs over the CURRENT page (bounded — never over the whole log).
  protected readonly actionCount = computed(
    () => new Set(this.events().map((e) => e.action)).size,
  );
  protected readonly actorCount = computed(
    () => new Set(this.events().map((e) => e.actor)).size,
  );
  protected readonly entityTypeCount = computed(
    () => new Set(this.events().map((e) => e.entity_type)).size,
  );

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

  constructor() {
    this.search$.pipe(debounceTime(300)).subscribe(() => {
      this.offset.set(0);
      this.load();
    });
  }

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    // The Admin-API returns audit events newest-first.
    this.adminService
      .getAudit({
        q: this.query.trim() || undefined,
        limit: this.pageSize(),
        offset: this.offset(),
      })
      .subscribe({
        next: (response) => {
          this.events.set(response.items);
          this.total.set(response.page.total);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Unable to load audit history. Is the Admin-API running on :8002?');
          this.events.set([]);
          this.total.set(0);
          this.loading.set(false);
        },
      });
  }

  onQueryChange(): void {
    this.search$.next();
  }

  clearSearch(): void {
    this.query = '';
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

  /** CSS modifier for an action badge (info by default, brand for updates). */
  actionBadgeClass(action: string): string {
    const a = action.toLowerCase();
    if (a.includes('delete') || a.includes('fail')) {
      return 'badge badge--high';
    }
    if (a.includes('create') || a.includes('enable')) {
      return 'badge badge--success';
    }
    return 'badge badge--info';
  }

  formatDetails(details: Record<string, unknown>): string {
    if (!details || Object.keys(details).length === 0) {
      return '—';
    }
    return JSON.stringify(details);
  }
}
