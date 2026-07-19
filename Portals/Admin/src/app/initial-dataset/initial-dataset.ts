import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { Subscription, interval, switchMap } from 'rxjs';

import { DatasetState, DatasetStatus } from '../models/admin';
import { AdminService } from '../services/admin.service';

const POLL_INTERVAL_MS = 4000;

/**
 * Initial Dataset view: shows the managed dataset's acquisition status and lets
 * an admin trigger the download. While the dataset is DOWNLOADING it polls the
 * Admin-API every ~4s, stopping when the state becomes DOWNLOADED or FAILED.
 */
@Component({
  selector: 'app-initial-dataset',
  imports: [],
  templateUrl: './initial-dataset.html',
  styleUrl: './initial-dataset.css',
})
export class InitialDataset implements OnInit, OnDestroy {
  protected readonly status = signal<DatasetStatus | null>(null);
  protected readonly loading = signal(false);
  protected readonly triggering = signal(false);
  protected readonly error = signal<string | null>(null);

  /** True while the dataset is actively downloading. */
  protected readonly isDownloading = computed(() => this.status()?.state === 'DOWNLOADING');

  /** The download button is disabled while DOWNLOADING or already DOWNLOADED. */
  protected readonly downloadDisabled = computed(() => {
    const state = this.status()?.state;
    return this.triggering() || state === 'DOWNLOADING' || state === 'DOWNLOADED';
  });

  /** Percentage complete for the progress bar (0–100), when size is known. */
  protected readonly progressPct = computed(() => {
    const s = this.status();
    if (!s || s.size_bytes <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((s.downloaded_bytes / s.size_bytes) * 100));
  });

  private pollSub: Subscription | null = null;

  constructor(private readonly adminService: AdminService) {}

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.adminService.getDatasetStatus().subscribe({
      next: (response) => {
        this.applyStatus(response);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load dataset status. Is the Admin-API running on :8002?');
        this.status.set(null);
        this.loading.set(false);
        this.stopPolling();
      },
    });
  }

  download(): void {
    this.triggering.set(true);
    this.error.set(null);
    this.adminService.triggerDatasetDownload('admin').subscribe({
      next: (response) => {
        this.applyStatus(response);
        this.triggering.set(false);
      },
      error: () => {
        this.error.set('Unable to trigger the download. Is the Admin-API running on :8002?');
        this.triggering.set(false);
      },
    });
  }

  /** Store a fresh status and (re)configure polling based on its state. */
  private applyStatus(status: DatasetStatus): void {
    this.status.set(status);
    if (status.state === 'DOWNLOADING') {
      this.startPolling();
    } else {
      this.stopPolling();
    }
  }

  private startPolling(): void {
    if (this.pollSub) {
      return;
    }
    this.pollSub = interval(POLL_INTERVAL_MS)
      .pipe(switchMap(() => this.adminService.getDatasetStatus()))
      .subscribe({
        next: (response) => {
          this.status.set(response);
          if (response.state === 'DOWNLOADED' || response.state === 'FAILED') {
            this.stopPolling();
          }
        },
        error: () => {
          this.error.set('Lost contact with the Admin-API while polling. Retry with Refresh.');
          this.stopPolling();
        },
      });
  }

  private stopPolling(): void {
    this.pollSub?.unsubscribe();
    this.pollSub = null;
  }

  /** Human-readable byte size, e.g. 5.8 GB. */
  formatBytes(bytes: number): string {
    if (bytes == null || bytes <= 0) {
      return '—';
    }
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    const rounded = value >= 10 || unit === 0 ? Math.round(value) : Math.round(value * 10) / 10;
    return `${rounded} ${units[unit]}`;
  }

  /** CSS modifier for the state badge. */
  badgeClass(state: DatasetState): string {
    return `badge badge--${state.toLowerCase().replace(/_/g, '-')}`;
  }
}
