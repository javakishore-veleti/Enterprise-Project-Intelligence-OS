import { Injectable, signal } from '@angular/core';

import { Organization } from '../models/org';

const STORAGE_KEY = 'admin.org.selected';

/**
 * The shared "currently-selected organization" context for the Organizations
 * area. Members / Repositories / Effective Access are per-org standalone pages
 * that all read this one selection, so switching from Members to Repositories
 * keeps the same org. The selection is persisted to localStorage so it survives
 * reloads and deep-links into a sub-page.
 */
@Injectable({ providedIn: 'root' })
export class OrgContextService {
  /** The org currently in context (null until one is picked). */
  readonly selected = signal<Organization | null>(this.restore());

  select(org: Organization): void {
    this.selected.set(org);
    this.persist(org);
  }

  clear(): void {
    this.selected.set(null);
    this.persist(null);
  }

  private persist(org: Organization | null): void {
    try {
      if (org) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(org));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // localStorage unavailable (private mode / SSR) — context stays in-memory.
    }
  }

  private restore(): Organization | null {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as Organization) : null;
    } catch {
      return null;
    }
  }
}
