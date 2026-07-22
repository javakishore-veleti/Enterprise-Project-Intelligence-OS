import { Component, OnInit, computed, signal } from '@angular/core';

import { AuditEvent } from '../models/admin';
import { AdminService } from '../services/admin.service';

@Component({
  selector: 'app-audit-list',
  imports: [],
  templateUrl: './audit-list.html',
  styleUrl: './audit-list.css',
})
export class AuditList implements OnInit {
  protected readonly events = signal<AuditEvent[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  /** KPI: distinct action types in the loaded window. */
  protected readonly actionCount = computed(
    () => new Set(this.events().map((e) => e.action)).size,
  );
  /** KPI: distinct actors in the loaded window. */
  protected readonly actorCount = computed(
    () => new Set(this.events().map((e) => e.actor)).size,
  );
  /** KPI: distinct entity types touched in the loaded window. */
  protected readonly entityTypeCount = computed(
    () => new Set(this.events().map((e) => e.entity_type)).size,
  );

  constructor(private readonly adminService: AdminService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    // The Admin-API returns audit events newest-first.
    this.adminService.getAudit({ limit: 100, offset: 0 }).subscribe({
      next: (response) => {
        this.events.set(response.items);
        this.total.set(response.page.total);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load audit history. Is the Admin-API running on :8002?');
        this.events.set([]);
        this.total.set(0);
        this.loading.set(false);
      },
    });
  }

  /** CSS modifier for an action badge (info by default, brand for updates). */
  actionBadgeClass(action: string): string {
    const a = action.toLowerCase();
    if (a.includes('delete') || a.includes('fail')) {
      return 'badge badge--high';
    }
    if (a.includes('create') || a.includes('enable')) {
      return 'badge badge--success';
    }
    return 'badge badge--info';
  }

  formatDetails(details: Record<string, unknown>): string {
    if (!details || Object.keys(details).length === 0) {
      return '—';
    }
    return JSON.stringify(details);
  }
}
