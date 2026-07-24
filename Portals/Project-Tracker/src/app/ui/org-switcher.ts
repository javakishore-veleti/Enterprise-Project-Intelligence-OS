import {
  Component,
  ElementRef,
  HostListener,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject, debounceTime, distinctUntilChanged, map, switchMap } from 'rxjs';

import { OrgNode, OrgService } from '../services/org.service';
import { OrgContextService } from './org-context.service';

/**
 * Organization-context switcher for the masthead — a searchable typeahead
 * picker that scales to thousands of orgs. A compact chip shows the current
 * context; clicking opens a popover with a debounced search input that queries
 * the server (`OrgService.searchOrgs`). It NEVER loads the whole tree: an empty
 * query shows only the bounded tenant roots, and typing searches all orgs
 * server-side. The visible list stays bounded (~20 results), so DOM and network
 * cost are flat in the number of organizations. Selecting an org persists it to
 * OrgContextService and reloads so every screen refetches with the new
 * X-Org-Key header — re-scoping the whole product. Adapts to its surroundings
 * (inherits text color); slate/azure accents, no violet.
 */
@Component({
  selector: 'app-org-switcher',
  imports: [FormsModule],
  template: `
    <div class="org">
      <button
        type="button"
        class="org__chip"
        [class.org__chip--open]="open()"
        (click)="toggle()"
        [attr.aria-expanded]="open()"
        aria-haspopup="listbox"
        title="Scope the whole product to an organization context."
      >
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M9 9h.01M9 12h.01M9 15h.01M15 9h.01M15 12h.01M15 15h.01"/></svg>
        <span class="org__label">{{ chipLabel() }}</span>
        <svg class="org__caret" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
      </button>

      @if (open()) {
        <div class="org__panel" role="dialog" aria-label="Choose organization scope">
          <div class="org__search">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>
            <input
              #searchBox
              type="text"
              [ngModel]="query()"
              (ngModelChange)="onQuery($event)"
              (keydown)="onKeydown($event)"
              placeholder="Search organizations…"
              autocomplete="off"
              spellcheck="false"
              aria-label="Search organizations"
            />
            @if (loading()) { <span class="org__spinner" aria-hidden="true"></span> }
          </div>

          <ul class="org__list" role="listbox">
            <li
              role="option"
              class="org__opt org__opt--clear"
              [class.is-active]="active() === -1"
              [attr.aria-selected]="ctx.currentOrgId() === null"
              (click)="clear()"
              (mouseenter)="active.set(-1)"
            >
              <span class="org__opt-name">All organizations (no scope)</span>
              @if (ctx.currentOrgId() === null) {
                <svg class="org__check" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              }
            </li>

            @if (!results().length && !loading()) {
              <li class="org__empty">
                {{ query().trim() ? 'No matching organizations.' : 'No organizations available.' }}
              </li>
            }

            @for (o of results(); track o.org_id; let i = $index) {
              <li
                role="option"
                class="org__opt"
                [class.is-active]="active() === i"
                [attr.aria-selected]="ctx.currentOrgId() === o.org_id"
                (click)="choose(o)"
                (mouseenter)="active.set(i)"
              >
                <div class="org__opt-main">
                  <span class="org__opt-name">{{ o.name }}</span>
                  @if (o.path && o.level > 1) {
                    <span class="org__opt-path">{{ o.path }}</span>
                  }
                </div>
                <span class="org__opt-level">L{{ o.level }}</span>
              </li>
            }
          </ul>

          @if (query().trim().length === 0) {
            <div class="org__hint">Showing tenant roots. Type to search all organizations.</div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: inline-flex; position: relative; }
    .org { display: inline-flex; position: relative; color: inherit; }

    .org__chip {
      display: inline-flex; align-items: center; gap: .4rem; color: inherit;
      background: color-mix(in srgb, currentColor 8%, transparent);
      border: 1px solid color-mix(in srgb, currentColor 22%, transparent);
      border-radius: 9px; padding: .5rem .55rem .5rem .6rem;
      font-size: .82rem; font-weight: 600; cursor: pointer; max-width: 15rem;
      transition: background .14s ease, border-color .14s ease;
    }
    .org__chip:hover { background: color-mix(in srgb, currentColor 14%, transparent); }
    .org__chip--open { border-color: #38bdf8; background: color-mix(in srgb, #38bdf8 16%, transparent); }
    .org__chip svg:first-child { flex: none; opacity: .85; }
    .org__label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .org__caret { flex: none; opacity: .7; }

    .org__panel {
      position: absolute; top: calc(100% + .4rem); right: 0; z-index: 60;
      width: 20rem; max-width: min(20rem, 92vw);
      background: #fff; color: #0f172a;
      border: 1px solid #e2e8f0; border-radius: 12px;
      box-shadow: 0 18px 40px -12px rgba(15,23,42,.35), 0 4px 12px -6px rgba(15,23,42,.2);
      overflow: hidden; animation: org-pop .12s ease;
    }
    @keyframes org-pop { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }

    .org__search {
      display: flex; align-items: center; gap: .45rem;
      padding: .6rem .7rem; border-bottom: 1px solid #eef2f7; color: #64748b;
    }
    .org__search svg { flex: none; }
    .org__search input {
      flex: 1; border: none; outline: none; background: transparent;
      font-size: .86rem; font-weight: 500; color: #0f172a; padding: 0;
    }
    .org__search input::placeholder { color: #94a3b8; }

    .org__spinner {
      flex: none; width: 13px; height: 13px; border-radius: 50%;
      border: 2px solid #cbd5e1; border-top-color: #0ea5e9;
      animation: org-spin .6s linear infinite;
    }
    @keyframes org-spin { to { transform: rotate(360deg); } }

    .org__list { list-style: none; margin: 0; padding: .3rem; max-height: 17rem; overflow-y: auto; }

    .org__opt {
      display: flex; align-items: center; gap: .5rem; justify-content: space-between;
      padding: .5rem .55rem; border-radius: 8px; cursor: pointer; font-size: .84rem;
    }
    .org__opt.is-active { background: #eff6ff; }
    .org__opt-main { display: flex; flex-direction: column; gap: .1rem; min-width: 0; }
    .org__opt-name { font-weight: 600; color: #0f172a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .org__opt-path { font-size: .72rem; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .org__opt-level { flex: none; font-size: .68rem; font-weight: 700; color: #0284c7; background: #e0f2fe; border-radius: 5px; padding: .1rem .3rem; }
    .org__opt--clear { color: #0f172a; font-weight: 600; border-bottom: 1px solid #f1f5f9; border-radius: 8px 8px 0 0; margin-bottom: .1rem; }
    .org__check { flex: none; color: #0284c7; }

    .org__empty { padding: .8rem .6rem; font-size: .82rem; color: #94a3b8; text-align: center; }
    .org__hint { padding: .5rem .7rem; font-size: .72rem; color: #94a3b8; border-top: 1px solid #eef2f7; background: #f8fafc; }
  `],
})
export class OrgSwitcher {
  protected readonly ctx = inject(OrgContextService);
  private readonly orgs = inject(OrgService);
  private readonly host = inject(ElementRef<HTMLElement>);

  protected readonly open = signal(false);
  protected readonly query = signal('');
  protected readonly loading = signal(false);
  protected readonly results = signal<OrgNode[]>([]);
  protected readonly active = signal(-1);

  /** Chip label: current org name, a stored id fallback, or the unscoped label. */
  protected readonly chipLabel = computed(() => {
    if (this.ctx.currentOrgId() === null) {
      return 'All organizations';
    }
    return this.ctx.currentOrgName() || this.ctx.currentOrgId() || 'Organization';
  });

  private readonly search$ = new Subject<string>();

  constructor() {
    // Debounced server-side search. An empty query loads bounded tenant roots
    // only — never the whole tree. Typing searches all orgs server-side.
    this.search$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap((q) => {
          this.loading.set(true);
          const trimmed = q.trim();
          return trimmed
            ? this.orgs.searchOrgs({ q: trimmed, limit: 20 })
            : this.orgs.roots().pipe(map((organizations) => ({ organizations, total: organizations.length })));
        }),
      )
      .subscribe({
        next: (res) => {
          this.results.set(res.organizations);
          this.active.set(-1);
          this.loading.set(false);
        },
        error: () => {
          this.results.set([]);
          this.active.set(-1);
          this.loading.set(false);
        },
      });

    // Restore the display name for an org seeded from localStorage (best-effort,
    // bounded: one search keyed on the stored id, not a tree load).
    effect(() => {
      const id = this.ctx.currentOrgId();
      if (id && !this.ctx.currentOrgName()) {
        this.orgs.searchOrgs({ q: id, limit: 5 }).subscribe({
          next: (res) => {
            const hit = res.organizations.find((o) => o.org_id === id);
            if (hit) {
              this.ctx.setOrg(id, hit.name);
            }
          },
          error: () => {},
        });
      }
    });
  }

  protected toggle(): void {
    const next = !this.open();
    this.open.set(next);
    if (next) {
      // Prime the list with bounded roots on open (empty query).
      this.query.set('');
      this.search$.next('');
      queueMicrotask(() => this.focusSearch());
    }
  }

  protected onQuery(q: string): void {
    this.query.set(q);
    this.search$.next(q);
  }

  protected choose(o: OrgNode): void {
    this.ctx.setOrg(o.org_id, o.name);
    this.reload();
  }

  protected clear(): void {
    this.ctx.setOrg(null, '');
    this.reload();
  }

  protected onKeydown(ev: KeyboardEvent): void {
    const items = this.results();
    switch (ev.key) {
      case 'ArrowDown':
        ev.preventDefault();
        this.active.set(Math.min(this.active() + 1, items.length - 1));
        break;
      case 'ArrowUp':
        ev.preventDefault();
        this.active.set(Math.max(this.active() - 1, -1));
        break;
      case 'Enter':
        ev.preventDefault();
        if (this.active() === -1) {
          this.clear();
        } else {
          const hit = items[this.active()];
          if (hit) {
            this.choose(hit);
          }
        }
        break;
      case 'Escape':
        ev.preventDefault();
        this.open.set(false);
        break;
    }
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(ev: MouseEvent): void {
    if (this.open() && !this.host.nativeElement.contains(ev.target as Node)) {
      this.open.set(false);
    }
  }

  private focusSearch(): void {
    const el = this.host.nativeElement.querySelector('input') as HTMLInputElement | null;
    el?.focus();
  }

  private reload(): void {
    // Reload so every screen refetches with the new X-Org-Key header, re-scoping
    // the entire product. Persistence happens before the reload.
    window.location.reload();
  }
}
