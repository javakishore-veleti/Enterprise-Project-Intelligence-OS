import { Component, OnInit, signal } from '@angular/core';

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

  formatDetails(details: Record<string, unknown>): string {
    if (!details || Object.keys(details).length === 0) {
      return '—';
    }
    return JSON.stringify(details);
  }
}
