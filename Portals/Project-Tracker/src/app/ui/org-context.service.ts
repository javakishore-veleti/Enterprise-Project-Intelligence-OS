import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'org.currentOrgId';

/**
 * Global org context for the session. The selected org id (or null = no scope)
 * is persisted to localStorage and mirrored into every request to the data APIs
 * via the org-scope HTTP interceptor. Changing it re-scopes the whole product.
 */
@Injectable({ providedIn: 'root' })
export class OrgContextService {
  /** Selected org id, or null for "All organizations (no scope)". */
  readonly currentOrgId = signal<string | null>(readStored());

  /** Display name of the selected org (for masthead / labels); '' when unscoped. */
  readonly currentOrgName = signal<string>('');

  setOrg(orgId: string | null, name = ''): void {
    this.currentOrgId.set(orgId);
    this.currentOrgName.set(orgId ? name : '');
    try {
      if (orgId) {
        localStorage.setItem(STORAGE_KEY, orgId);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // localStorage may be unavailable (private mode / SSR) — scope stays in-memory.
    }
  }
}

function readStored(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}
