import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { VisibleProject } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';
import { OrgPicker } from '../org-picker/org-picker';

/**
 * Effective Access page (route: /organizations/access). Standalone, full-width.
 * Resolves the exact set of tracker projects visible to a user subject — the net
 * result of memberships, repository visibility scopes and grants across every
 * org. Shows the org picker for consistency with the other org sub-pages, and
 * pre-fills the subject search from the selected org's members is left to the
 * operator (subject-scoped resolution is tenant-wide by design).
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

  protected accessSubject = '';
  protected readonly accessProjects = signal<VisibleProject[] | null>(null);
  protected readonly accessLoading = signal(false);
  protected readonly accessError = signal<string | null>(null);
  protected readonly accessResolvedSubject = signal<string | null>(null);

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
        this.accessError.set(
          this.errMessage(err, 'Unable to resolve visible projects. Is the Org-Management-API running on :8005?'),
        );
      },
    });
  }

  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    return body?.error?.message ?? fallback;
  }
}
