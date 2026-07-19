import { Component, OnInit, computed, signal } from '@angular/core';

import { SystemHealth as SystemHealthModel } from '../models/admin';
import { AdminService } from '../services/admin.service';

@Component({
  selector: 'app-system-health',
  imports: [],
  templateUrl: './system-health.html',
  styleUrl: './system-health.css',
})
export class SystemHealth implements OnInit {
  protected readonly health = signal<SystemHealthModel | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly dependencies = computed(() => {
    const h = this.health();
    if (!h) {
      return [] as { name: string; status: string }[];
    }
    return Object.entries(h.dependencies).map(([name, status]) => ({ name, status }));
  });

  constructor(private readonly adminService: AdminService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.adminService.getSystemHealth().subscribe({
      next: (response) => {
        this.health.set(response);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load system health. Is the Admin-API running on :8002?');
        this.health.set(null);
        this.loading.set(false);
      },
    });
  }

  isOk(status: string): boolean {
    return status.toLowerCase() === 'ok' || status.toLowerCase() === 'healthy';
  }
}
