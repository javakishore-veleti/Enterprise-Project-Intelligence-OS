import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { OrgNode, OrgService } from '../services/org.service';
import { OrgContextService } from './org-context.service';

interface OrgOption {
  id: string;
  label: string;
}

/**
 * Organization-context switcher for the masthead. Lists "All organizations
 * (no scope)" plus the full org tree (options indented by level). Selecting an
 * org persists it to OrgContextService and reloads so every screen refetches
 * with the new X-Org-Key header — re-scoping the entire product to that org's
 * visible projects. Adapts to its surroundings (inherits text color).
 */
@Component({
  selector: 'app-org-switcher',
  imports: [FormsModule],
  template: `
    <label class="org" title="Scope the whole product to an organization context.">
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M9 9h.01M9 12h.01M9 15h.01M15 9h.01M15 12h.01M15 15h.01"/></svg>
      <select [ngModel]="ctx.currentOrgId() ?? ''" (ngModelChange)="onSelect($event)">
        <option value="">All organizations (no scope)</option>
        @for (o of options(); track o.id) {
          <option [value]="o.id">{{ o.label }}</option>
        }
      </select>
    </label>
  `,
  styles: [`
    :host { display: inline-flex; }
    .org {
      display: inline-flex; align-items: center; gap: .4rem; color: inherit;
      background: color-mix(in srgb, currentColor 8%, transparent);
      border: 1px solid color-mix(in srgb, currentColor 22%, transparent);
      border-radius: 9px; padding: 0 .3rem 0 .6rem;
    }
    .org svg { flex: none; opacity: .85; }
    .org select {
      width: auto; background: transparent; border: none; color: inherit;
      font-size: .82rem; font-weight: 600; padding: .5rem .3rem; cursor: pointer; box-shadow: none;
    }
    .org select:focus { outline: none; }
    .org option { color: #0f172a; }
  `],
})
export class OrgSwitcher {
  protected readonly ctx = inject(OrgContextService);
  private readonly orgs = inject(OrgService);

  protected readonly options = signal<OrgOption[]>([]);
  private readonly byId = new Map<string, string>();

  constructor() {
    this.orgs.tree().subscribe({
      next: (nodes) => {
        this.options.set(nodes.map((n) => this.toOption(n)));
        for (const n of nodes) {
          this.byId.set(n.org_id, n.name);
        }
        // Restore the display name for an org seeded from localStorage.
        const current = this.ctx.currentOrgId();
        if (current && this.byId.has(current)) {
          this.ctx.setOrg(current, this.byId.get(current)!);
        }
      },
      error: () => this.options.set([]),
    });
  }

  protected onSelect(id: string): void {
    const orgId = id || null;
    this.ctx.setOrg(orgId, orgId ? (this.byId.get(orgId) ?? '') : '');
    // Reload so every screen refetches with the new X-Org-Key header, re-scoping
    // the entire product. Persistence above happens before the reload.
    window.location.reload();
  }

  private toOption(n: OrgNode): OrgOption {
    const indent = '— '.repeat(Math.max(0, n.level - 1));
    return { id: n.org_id, label: `${indent}${n.name}` };
  }
}
