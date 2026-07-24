import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { VisibleProject } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';
import { OrgPicker } from '../org-picker/org-picker';

/** Page sizes offered by the selector — bounded regardless of total. */
const PAGE_SIZES = [25, 50, 100] as const;

/**
 * Effective Access page (route: /organizations/access). Standalone, full-width.
 * Resolves the exact set of tracker projects visible to a user subject — the net
 * result of memberships, repository visibility scopes and grants across every
 * org. A subject's visible set can be huge, so the results are a SERVER-PAGED +
 * SEARCHABLE table: only the current page of projects is rendered
 * (page-replacement), the `total` comes from the endpoint's cheap COUNT, and a
 * debounced filter (`q` on external_key / name) runs server-side.
 */
@Component({
  selector: 'app-org-access',
  imports: [FormsModule, OrgPicker],
  templateUrl: './org-access.html',
  styleUrls: ['../org.css'],
})
export class OrgAccess {
  private readonly orgAdmin = inject(OrgAdminService);
  protected readonly ctx = inject(OrgContextService);

  protected readonly pageSizes = PAGE_SIZES;

  protected accessSubject = '';
  // Current page of visible projects (replaced per page — never accumulated).
  protected readonly projects = signal<VisibleProject[] | null>(null);
  protected readonly total = signal(0);
  protected readonly offset = signal(0);
  protected readonly pageSize = signal<number>(PAGE_SIZES[0]);
  protected readonly accessLoading = signal(false);
  protected readonly accessError = signal<string | null>(null);
  protected readonly resolvedSubject = signal<string | null>(null);

  // The subject actually being paged (so Prev/Next/search reuse it).
  private activeSubject: string | null = null;

  // In-results filter (server-side, debounced; resets to page 0).
  protected filter = '';
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

  constructor() {
    this.filter$.pipe(debounceTime(300)).subscribe(() => {
      this.offset.set(0);
      this.load();
    });
  }

  /** Resolve (or re-resolve) from the subject box — starts at page 0. */
  resolveAccess(): void {
    const subject = this.accessSubject.trim();
    if (!subject) {
      return;
    }
    this.activeSubject = subject;
    this.filter = '';
    this.offset.set(0);
    this.load();
  }

  private load(): void {
    const subject = this.activeSubject;
    if (!subject) {
      return;
    }
    this.accessLoading.set(true);
    this.accessError.set(null);
    this.orgAdmin
      .visibleProjects(subject, {
        q: this.filter.trim() || undefined,
        limit: this.pageSize(),
        offset: this.offset(),
      })
      .subscribe({
        next: (resp) => {
          this.accessLoading.set(false);
          this.projects.set(resp.projects);
          this.total.set(resp.total ?? resp.projects.length);
          this.resolvedSubject.set(resp.subject);
        },
        error: (err: HttpErrorResponse) => {
          this.accessLoading.set(false);
          this.projects.set(null);
          this.total.set(0);
          this.accessError.set(
            this.errMessage(err, 'Unable to resolve visible projects. Is the Org-Management-API running on :8005?'),
          );
        },
      });
  }

  onFilterChange(): void {
    this.filter$.next();
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

  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    return body?.error?.message ?? fallback;
  }
}
