import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { AddMemberRequest, Member, ROLE_OPTIONS } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { NotificationService } from '../../ui/notification.service';

const PAGE_SIZE = 25;

/**
 * Members & Roles page (route: /organizations/:orgId/members). Server-paged +
 * searchable + role-filterable — never loads all members. Each row shows the
 * member's DIRECT roles and the roles INHERITED from ancestor orgs (badged with
 * their source), so the inheritance chain is visible.
 */
@Component({
  selector: 'app-org-members',
  imports: [FormsModule],
  templateUrl: './org-members.html',
  styleUrls: ['../org.css'],
})
export class OrgMembers implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly orgAdmin = inject(OrgAdminService);
  private readonly notifications = inject(NotificationService);

  protected readonly roleOptions = ROLE_OPTIONS;

  protected readonly orgId = signal<string>('');
  protected readonly members = signal<Member[]>([]);
  protected readonly total = signal(0);
  protected readonly offset = signal(0);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly limit = PAGE_SIZE;

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

  ngOnInit(): void {
    this.search$.pipe(debounceTime(300)).subscribe(() => {
      this.offset.set(0);
      this.load();
    });
    this.route.paramMap.subscribe((pm) => {
      this.orgId.set(pm.get('orgId') ?? '');
      this.offset.set(0);
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
    this.orgAdmin
      .listMembers(id, {
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
    const id = this.orgId();
    const subject = this.memberSubject.trim();
    if (!id || !subject) {
      return;
    }
    this.addingMember.set(true);
    const body: AddMemberRequest = {
      subject,
      roles: [...this.memberRoles],
      inherits_down: this.memberInherits,
    };
    this.orgAdmin.addMember(id, body).subscribe({
      next: (member) => {
        this.addingMember.set(false);
        this.memberSubject = '';
        this.memberRoles = [];
        this.memberInherits = true;
        this.notifications.success('Member added', `${member.subject} added to this organization.`);
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
