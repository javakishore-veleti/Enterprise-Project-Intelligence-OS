import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { AddMemberRequest, Member, ROLE_OPTIONS } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';
import { NotificationService } from '../../ui/notification.service';
import { OrgPicker } from '../org-picker/org-picker';

const PAGE_SIZE = 25;

/**
 * Members & Roles page (route: /organizations/members). Standalone, full-width,
 * operating on the shared selected-org context. Server-paged + searchable +
 * role-filterable — never loads all members. Each row shows DIRECT roles and
 * roles INHERITED from ancestor orgs (badged with their source).
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

  protected readonly roleOptions = ROLE_OPTIONS;

  protected readonly members = signal<Member[]>([]);
  protected readonly total = signal(0);
  protected readonly offset = signal(0);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly limit = PAGE_SIZE;
  private lastId: string | null = null;

  // Filters
  protected query = '';
  protected roleFilter = '';
  private readonly search$ = new Subject<void>();

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

  constructor() {
    this.search$.pipe(debounceTime(300)).subscribe(() => {
      this.offset.set(0);
      this.load();
    });
    effect(() => {
      const sel = this.ctx.selected();
      untracked(() => {
        const id = sel?.org_id ?? null;
        if (id !== this.lastId) {
          this.lastId = id;
          this.query = '';
          this.roleFilter = '';
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

  onRoleFilterChange(): void {
    this.offset.set(0);
    this.load();
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
