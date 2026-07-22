import { Injectable, computed, signal } from '@angular/core';

export interface ScopeUser {
  key: string;
  label: string;
}

/**
 * Global identity/scope for the session. Set once (masthead switcher = demo
 * impersonation; SSO subject in production); every page scopes to it.
 */
@Injectable({ providedIn: 'root' })
export class UserScopeService {
  readonly users: ReadonlyArray<ScopeUser> = [
    { key: '', label: 'Director — all projects' },
    { key: 'mgr-apac', label: 'APAC Delivery Manager' },
    { key: 'mgr-data', label: 'Data Platform Manager' },
  ];

  readonly userKey = signal<string>('');
  readonly label = computed(() => this.users.find((u) => u.key === this.userKey())?.label ?? '');

  setUser(key: string): void {
    this.userKey.set(key);
  }
}
