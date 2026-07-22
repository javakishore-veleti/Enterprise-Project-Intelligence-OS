import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { UserScopeService } from './user-scope.service';

/**
 * Reusable identity/scope switcher (demo impersonation → SSO in production).
 * Drop `<app-scope-switcher>` anywhere; it reads/writes the shared UserScopeService,
 * and adapts to its surroundings (inherits text color). Not hardcoded per page.
 */
@Component({
  selector: 'app-scope-switcher',
  imports: [FormsModule],
  template: `
    <label class="scope" title="Impersonate a user (demo). In production this is your SSO identity.">
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/></svg>
      <select [ngModel]="scope.userKey()" (ngModelChange)="scope.setUser($event)">
        @for (u of scope.users; track u.key) { <option [value]="u.key">{{ u.label }}</option> }
      </select>
    </label>
  `,
  styles: [`
    :host { display: inline-flex; }
    .scope {
      display: inline-flex; align-items: center; gap: .4rem; color: inherit;
      background: color-mix(in srgb, currentColor 8%, transparent);
      border: 1px solid color-mix(in srgb, currentColor 22%, transparent);
      border-radius: 9px; padding: 0 .3rem 0 .6rem;
    }
    .scope svg { flex: none; opacity: .85; }
    .scope select {
      width: auto; background: transparent; border: none; color: inherit;
      font-size: .82rem; font-weight: 600; padding: .5rem .3rem; cursor: pointer; box-shadow: none;
    }
    .scope select:focus { outline: none; }
    .scope option { color: #0f172a; }
  `],
})
export class ScopeSwitcher {
  protected readonly scope = inject(UserScopeService);
}
