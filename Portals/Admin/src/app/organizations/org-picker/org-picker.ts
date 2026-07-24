import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { Organization } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';
import { OrgContextService } from '../../services/org-context.service';

/**
 * The shared org picker bar shown at the top of every per-org page. It displays
 * the org currently in context and lets the operator switch to any other org via
 * the scalable server-side search — the selection persists (OrgContextService)
 * so moving between Profile / Sub-Orgs / Members / Repositories / Access keeps
 * the same org. When nothing is selected it opens straight into search.
 */
@Component({
  selector: 'app-org-picker',
  imports: [FormsModule],
  templateUrl: './org-picker.html',
  styleUrls: ['../org.css'],
})
export class OrgPicker implements OnInit {
  private readonly orgAdmin = inject(OrgAdminService);
  protected readonly ctx = inject(OrgContextService);

  protected readonly changing = signal(false);
  protected readonly showSearch = computed(() => this.changing() || this.ctx.selected() == null);

  protected query = '';
  protected readonly searchLoading = signal(false);
  protected readonly results = signal<Organization[]>([]);
  private readonly input$ = new Subject<string>();

  ngOnInit(): void {
    this.input$.pipe(debounceTime(300)).subscribe((q) => this.run(q));
  }

  toggleChange(): void {
    this.changing.update((v) => !v);
    if (this.changing()) {
      this.query = '';
      this.results.set([]);
    }
  }

  onInput(value: string): void {
    this.input$.next(value);
  }

  private run(q: string): void {
    const term = q.trim();
    if (!term) {
      this.results.set([]);
      return;
    }
    this.searchLoading.set(true);
    this.orgAdmin.searchOrgs(term, null, 25, 0).subscribe({
      next: (resp) => {
        this.results.set(resp.organizations);
        this.searchLoading.set(false);
      },
      error: () => {
        this.results.set([]);
        this.searchLoading.set(false);
      },
    });
  }

  pick(org: Organization): void {
    this.ctx.select(org);
    this.changing.set(false);
    this.query = '';
    this.results.set([]);
  }
}
