import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { CreateOrganizationRequest, Organization } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { NotificationService } from '../../ui/notification.service';

/**
 * Org Overview page (route: /organizations/:orgId). Shows the org's facts
 * (level, kind, path, child/member counts) and the structural actions —
 * rename, move (with the server-side cycle guard) and create-child. Loads only
 * this org; a create/move refreshes just this org's facts, never the whole tree.
 */
@Component({
  selector: 'app-org-overview',
  imports: [FormsModule],
  templateUrl: './org-overview.html',
  styleUrls: ['../org.css'],
})
export class OrgOverview implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly orgAdmin = inject(OrgAdminService);
  private readonly notifications = inject(NotificationService);

  protected readonly orgId = signal<string>('');
  protected readonly org = signal<Organization | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected renameName = '';
  protected renameKind = '';
  protected renaming = signal(false);

  protected childName = '';
  protected childKind = '';
  protected creatingChild = signal(false);

  protected moveTargetId = '';
  protected moving = signal(false);

  ngOnInit(): void {
    this.route.paramMap.subscribe((pm) => {
      const id = pm.get('orgId') ?? '';
      this.orgId.set(id);
      this.load(id);
    });
  }

  private load(id: string): void {
    if (!id) {
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.orgAdmin.getOrg(id).subscribe({
      next: (o) => {
        this.org.set(o);
        this.renameName = o.name;
        this.renameKind = o.kind ?? '';
        this.moveTargetId = '';
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load this organization. Is the Org-Management-API running on :8005?');
        this.org.set(null);
        this.loading.set(false);
      },
    });
  }

  async rename(): Promise<void> {
    const org = this.org();
    const name = this.renameName.trim();
    if (!org || !name) {
      return;
    }
    const kind = this.renameKind.trim() || null;
    if (name === org.name && kind === (org.kind ?? null)) {
      return;
    }
    const ok = await this.notifications.confirm({
      title: 'Rename organization?',
      message: `Rename "${org.name}" to "${name}"${kind ? ` (kind: ${kind})` : ''}.`,
      confirmLabel: 'Save',
    });
    if (!ok) {
      return;
    }
    this.renaming.set(true);
    this.orgAdmin.updateOrg(org.org_id, { name, kind }).subscribe({
      next: (updated) => {
        this.renaming.set(false);
        this.org.set(updated);
        this.notifications.success('Organization updated', `Now "${updated.name}".`);
      },
      error: (err: HttpErrorResponse) => {
        this.renaming.set(false);
        this.notifications.error('Update failed', this.errMessage(err, 'Could not rename the organization.'));
      },
    });
  }

  async createChild(): Promise<void> {
    const parent = this.org();
    const name = this.childName.trim();
    if (!parent || !name) {
      return;
    }
    const ok = await this.notifications.confirm({
      title: 'Create child organization?',
      message: `Create "${name}" under "${parent.name}" (level ${parent.level + 1}).`,
      confirmLabel: 'Create child',
    });
    if (!ok) {
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
        // Refresh only THIS org's facts (its child_count changed).
        this.load(parent.org_id);
      },
      error: (err: HttpErrorResponse) => {
        this.creatingChild.set(false);
        this.notifications.error('Create failed', this.errMessage(err, 'Could not create the child organization.'));
      },
    });
  }

  async move(): Promise<void> {
    const org = this.org();
    const target = this.moveTargetId.trim();
    if (!org || !target) {
      return;
    }
    const ok = await this.notifications.confirm({
      title: 'Move organization?',
      message: `Reparent "${org.name}" (and its whole subtree) under org ${target}. Moving a node beneath itself is rejected.`,
      confirmLabel: 'Move',
      danger: true,
    });
    if (!ok) {
      return;
    }
    this.moving.set(true);
    this.orgAdmin.moveOrg(org.org_id, { new_parent_org_id: target }).subscribe({
      next: (updated) => {
        this.moving.set(false);
        this.org.set(updated);
        this.moveTargetId = '';
        this.notifications.success('Organization moved', `"${updated.name}" is now at level ${updated.level}.`);
      },
      error: (err: HttpErrorResponse) => {
        this.moving.set(false);
        this.notifications.error('Move rejected', this.errMessage(err, 'Could not move the organization.'));
      },
    });
  }

  openTree(): void {
    this.router.navigate(['/organizations']);
  }

  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    return body?.error?.message ?? fallback;
  }
}
