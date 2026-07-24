import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { CreateOrganizationRequest, Organization } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';
import { NotificationService } from '../../ui/notification.service';

/**
 * Organizations landing (route: /organizations). The entry point that picks a
 * starting org: lists tenant roots + a scalable search, and creates new roots.
 * Choosing one sets the shared org context and drops into its Sub-Organizations.
 * If an org is already in context, jumps straight there.
 */
@Component({
  selector: 'app-org-landing',
  imports: [FormsModule],
  templateUrl: './org-landing.html',
  styleUrls: ['../org.css'],
})
export class OrgLanding implements OnInit {
  private readonly orgAdmin = inject(OrgAdminService);
  private readonly ctx = inject(OrgContextService);
  private readonly router = inject(Router);
  private readonly notifications = inject(NotificationService);

  protected readonly roots = signal<Organization[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected searchQuery = '';
  protected readonly searching = signal(false);
  protected readonly searchLoading = signal(false);
  protected readonly searchResults = signal<Organization[]>([]);
  private readonly input$ = new Subject<string>();

  protected rootName = '';
  protected rootKind = '';
  protected creatingRoot = signal(false);

  ngOnInit(): void {
    if (this.ctx.selected()) {
      this.router.navigate(['/organizations/sub-orgs']);
      return;
    }
    this.input$.pipe(debounceTime(300)).subscribe((q) => this.runSearch(q));
    this.loadRoots();
  }

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

  onSearchChange(value: string): void {
    this.input$.next(value);
  }

  private runSearch(q: string): void {
    const term = q.trim();
    if (!term) {
      this.searching.set(false);
      this.searchResults.set([]);
      return;
    }
    this.searching.set(true);
    this.searchLoading.set(true);
    this.orgAdmin.searchOrgs(term, null, 25, 0).subscribe({
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

  /** Set the chosen org as context and drop into its Sub-Organizations. */
  choose(org: Organization): void {
    this.ctx.select(org);
    this.router.navigate(['/organizations/sub-orgs']);
  }

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
        this.choose(org);
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
