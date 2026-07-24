import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { AddMemberRequest, Member } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';
import { NotificationService } from '../../ui/notification.service';
import { OrgPicker } from '../org-picker/org-picker';

const PAGE_SIZE = 25;
/** Cap for the role typeahead (matches the API's ≤50 cap). */
const ROLE_SUGGEST_LIMIT = 25;

/**
 * Members & Roles page (route: /organizations/members). Standalone, full-width,
 * operating on the shared selected-org context. Server-paged + searchable +
 * role-filterable — never loads all members. Each row shows DIRECT roles and
 * roles INHERITED from ancestor orgs (badged with their source).
 *
 * Roles are chosen through a SEARCHABLE typeahead sourced from `GET /roles`
 * (distinct role names, filtered + capped) rather than a scrollable <select>,
 * so an org with a large role catalog stays usable. Free-typing a brand-new
 * role is still allowed (roles are free text).
 */
@Component({
  selector: 'app-org-members',
  imports: [FormsModule, OrgPicker],
  templateUrl: './org-members.html',
  styleUrls: ['../org.css'],
})
export class OrgMembers {
  private readonly orgAdmin = inject(OrgAdminService);
  protected readonly ctx = inject(OrgContextService);
  private readonly notifications = inject(NotificationService);

  protected readonly members = signal<Member[]>([]);
  protected readonly total = signal(0);
  protected readonly offset = signal(0);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly limit = PAGE_SIZE;
  private lastId: string | null = null;

  // Filters
  protected query = '';
  protected roleFilter = ''; // applied role filter ('' = all roles)
  private readonly search$ = new Subject<void>();

  // Role FILTER typeahead
  protected filterRoleQuery = '';
  protected readonly filterRoleOpen = signal(false);
  protected readonly filterRoleLoading = signal(false);
  protected readonly filterRoleResults = signal<string[]>([]);
  private readonly filterRole$ = new Subject<string>();

  // Add-member ROLE typeahead (multi-select chips)
  protected addRoleQuery = '';
  protected readonly addRoleOpen = signal(false);
  protected readonly addRoleLoading = signal(false);
  protected readonly addRoleResults = signal<string[]>([]);
  private readonly addRole$ = new Subject<string>();

  // Paging display helpers
  protected readonly rangeStart = computed(() => (this.total() === 0 ? 0 : this.offset() + 1));
  protected readonly rangeEnd = computed(() => Math.min(this.offset() + this.limit, this.total()));
  protected readonly canPrev = computed(() => this.offset() > 0);
  protected readonly canNext = computed(() => this.offset() + this.limit < this.total());

  // Add-member form
  protected memberSubject = '';
  protected memberRoles: string[] = [];
  protected memberInherits = true;
  protected addingMember = signal(false);

  // "Add new role" affordance: query is non-empty and not already an exact
  // (case-insensitive) match among the suggestions or the picked chips.
  protected readonly canAddTypedRole = computed(() => {
    const typed = this.addRoleQuery.trim();
    if (!typed) {
      return false;
    }
    const lc = typed.toLowerCase();
    const inChips = this.memberRoles.some((r) => r.toLowerCase() === lc);
    const inResults = this.addRoleResults().some((r) => r.toLowerCase() === lc);
    return !inChips && !inResults;
  });

  constructor() {
    this.search$.pipe(debounceTime(300)).subscribe(() => {
      this.offset.set(0);
      this.load();
    });
    this.filterRole$.pipe(debounceTime(300)).subscribe((q) => this.runFilterRoleSearch(q));
    this.addRole$.pipe(debounceTime(300)).subscribe((q) => this.runAddRoleSearch(q));
    effect(() => {
      const sel = this.ctx.selected();
      untracked(() => {
        const id = sel?.org_id ?? null;
        if (id !== this.lastId) {
          this.lastId = id;
          this.query = '';
          this.clearRoleFilter();
          this.offset.set(0);
          this.load();
        }
      });
    });
  }

  private load(): void {
    const org = this.ctx.selected();
    if (!org) {
      this.members.set([]);
      this.total.set(0);
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.orgAdmin
      .listMembers(org.org_id, {
        q: this.query.trim() || undefined,
        role: this.roleFilter || undefined,
        limit: this.limit,
        offset: this.offset(),
      })
      .subscribe({
        next: (resp) => {
          this.members.set(resp.members);
          this.total.set(resp.total ?? resp.members.length);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Unable to load members.');
          this.members.set([]);
          this.total.set(0);
          this.loading.set(false);
        },
      });
  }

  onQueryChange(): void {
    this.search$.next();
  }

  // --- Role FILTER typeahead -------------------------------------------------

  onFilterRoleInput(): void {
    this.filterRole$.next(this.filterRoleQuery);
  }

  private runFilterRoleSearch(q: string): void {
    const term = q.trim();
    this.filterRoleLoading.set(true);
    this.filterRoleOpen.set(true);
    this.orgAdmin.roles(term, ROLE_SUGGEST_LIMIT).subscribe({
      next: (resp) => {
        this.filterRoleResults.set(resp.roles);
        this.filterRoleLoading.set(false);
      },
      error: () => {
        this.filterRoleResults.set([]);
        this.filterRoleLoading.set(false);
      },
    });
  }

  openFilterRoles(): void {
    // Prime with the top roles on focus (empty query = first page).
    this.runFilterRoleSearch(this.filterRoleQuery);
  }

  pickRoleFilter(role: string): void {
    this.roleFilter = role;
    this.filterRoleQuery = role;
    this.filterRoleOpen.set(false);
    this.offset.set(0);
    this.load();
  }

  clearRoleFilter(): void {
    this.roleFilter = '';
    this.filterRoleQuery = '';
    this.filterRoleResults.set([]);
    this.filterRoleOpen.set(false);
    this.offset.set(0);
    this.load();
  }

  closeFilterRolesSoon(): void {
    // Delay so a click on a suggestion registers before the list closes.
    setTimeout(() => this.filterRoleOpen.set(false), 150);
  }

  // --- Add-member ROLE typeahead (chips) ------------------------------------

  onAddRoleInput(): void {
    this.addRole$.next(this.addRoleQuery);
  }

  private runAddRoleSearch(q: string): void {
    const term = q.trim();
    this.addRoleLoading.set(true);
    this.addRoleOpen.set(true);
    this.orgAdmin.roles(term, ROLE_SUGGEST_LIMIT).subscribe({
      next: (resp) => {
        // Hide roles already picked as chips.
        this.addRoleResults.set(resp.roles.filter((r) => !this.memberRoles.includes(r)));
        this.addRoleLoading.set(false);
      },
      error: () => {
        this.addRoleResults.set([]);
        this.addRoleLoading.set(false);
      },
    });
  }

  openAddRoles(): void {
    this.runAddRoleSearch(this.addRoleQuery);
  }

  addRoleValue(role: string): void {
    const value = role.trim();
    if (!value) {
      return;
    }
    if (!this.memberRoles.some((r) => r.toLowerCase() === value.toLowerCase())) {
      this.memberRoles = [...this.memberRoles, value];
    }
    this.addRoleQuery = '';
    this.addRoleResults.set([]);
    this.addRoleOpen.set(false);
  }

  addTypedRole(): void {
    this.addRoleValue(this.addRoleQuery);
  }

  removeRole(role: string): void {
    this.memberRoles = this.memberRoles.filter((r) => r !== role);
  }

  closeAddRolesSoon(): void {
    setTimeout(() => this.addRoleOpen.set(false), 150);
  }

  prev(): void {
    if (this.canPrev()) {
      this.offset.set(Math.max(0, this.offset() - this.limit));
      this.load();
    }
  }

  next(): void {
    if (this.canNext()) {
      this.offset.set(this.offset() + this.limit);
      this.load();
    }
  }

  addMember(): void {
    const org = this.ctx.selected();
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
        this.addRoleQuery = '';
        this.memberInherits = true;
        this.notifications.success('Member added', `${member.subject} added to ${org.name}.`);
        this.offset.set(0);
        this.load();
      },
      error: (err: HttpErrorResponse) => {
        this.addingMember.set(false);
        this.notifications.error('Add member failed', this.errMessage(err, 'Could not add the member.'));
      },
    });
  }

  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    return body?.error?.message ?? fallback;
  }
}
