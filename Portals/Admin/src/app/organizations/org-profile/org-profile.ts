import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Organization } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';
import { NotificationService } from '../../ui/notification.service';
import { OrgPicker } from '../org-picker/org-picker';

/**
 * Profile page (route: /organizations/profile) — the selected org's own page:
 * name, kind, level, path, child/member counts, plus edit actions (rename,
 * change kind, move with the server-side cycle guard). Operates on the shared
 * org context; switching org via the picker reloads this page's org.
 */
@Component({
  selector: 'app-org-profile',
  imports: [FormsModule, OrgPicker],
  templateUrl: './org-profile.html',
  styleUrls: ['../org.css'],
})
export class OrgProfile {
  private readonly orgAdmin = inject(OrgAdminService);
  protected readonly ctx = inject(OrgContextService);
  private readonly notifications = inject(NotificationService);

  protected readonly org = signal<Organization | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  private lastId: string | null = null;

  protected editName = '';
  protected editKind = '';
  protected saving = signal(false);

  protected moveTargetId = '';
  protected moving = signal(false);

  constructor() {
    // Reload whenever the selected org CHANGES (by id) — not on same-id refreshes.
    effect(() => {
      const sel = this.ctx.selected();
      untracked(() => {
        const id = sel?.org_id ?? null;
        if (id !== this.lastId) {
          this.lastId = id;
          this.load(id);
        }
      });
    });
  }

  private load(id: string | null): void {
    if (!id) {
      this.org.set(null);
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.orgAdmin.getOrg(id).subscribe({
      next: (o) => {
        this.org.set(o);
        this.editName = o.name;
        this.editKind = o.kind ?? '';
        this.moveTargetId = '';
        this.loading.set(false);
        // Keep the shared context fresh (same id ⇒ no reload loop).
        this.ctx.select(o);
      },
      error: () => {
        this.error.set('Unable to load this organization. Is the Org-Management-API running on :8005?');
        this.org.set(null);
        this.loading.set(false);
      },
    });
  }

  async save(): Promise<void> {
    const org = this.org();
    const name = this.editName.trim();
    if (!org || !name) {
      return;
    }
    const kind = this.editKind.trim() || null;
    if (name === org.name && kind === (org.kind ?? null)) {
      return;
    }
    const ok = await this.notifications.confirm({
      title: 'Save organization changes?',
      message: `Update "${org.name}" → name "${name}"${kind ? `, kind "${kind}"` : ''}.`,
      confirmLabel: 'Save',
    });
    if (!ok) {
      return;
    }
    this.saving.set(true);
    this.orgAdmin.updateOrg(org.org_id, { name, kind }).subscribe({
      next: (updated) => {
        this.saving.set(false);
        this.org.set(updated);
        this.ctx.select(updated);
        this.notifications.success('Organization updated', `Now "${updated.name}".`);
      },
      error: (err: HttpErrorResponse) => {
        this.saving.set(false);
        this.notifications.error('Update failed', this.errMessage(err, 'Could not update the organization.'));
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
        this.ctx.select(updated);
        this.moveTargetId = '';
        this.notifications.success('Organization moved', `"${updated.name}" is now at level ${updated.level}.`);
      },
      error: (err: HttpErrorResponse) => {
        this.moving.set(false);
        this.notifications.error('Move rejected', this.errMessage(err, 'Could not move the organization.'));
      },
    });
  }

  private errMessage(err: HttpErrorResponse, fallback: string): string {
    const body = err?.error as { error?: { message?: string } } | undefined;
    return body?.error?.message ?? fallback;
  }
}
