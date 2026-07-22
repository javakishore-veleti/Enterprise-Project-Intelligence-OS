import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { Subscription, interval, switchMap } from 'rxjs';

import {
  DatasetState,
  DatasetStatus,
  IngestionProgress,
  IngestionStatus,
} from '../models/admin';
import { AdminService } from '../services/admin.service';
import { NotificationService } from '../ui/notification.service';

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

  // --- Ingestion into the evidence store -----------------------------------

  protected readonly ingestion = signal<IngestionProgress | null>(null);
  protected readonly ingesting = signal(false);
  protected readonly ingestionError = signal<string | null>(null);

  /** True while an ingestion run is actively pending/running. */
  protected readonly ingestionActive = computed(() => {
    const s = this.ingestion()?.status;
    return s === 'PENDING' || s === 'RUNNING';
  });

  /**
   * The ingest button is enabled ONLY when the dataset is DOWNLOADED and no run
   * is in flight — i.e. ingestion is NOT_STARTED or FAILED (retry).
   */
  protected readonly ingestDisabled = computed(() => {
    if (this.ingesting()) {
      return true;
    }
    if (this.status()?.state !== 'DOWNLOADED') {
      return true;
    }
    const status = this.ingestion()?.status ?? 'NOT_STARTED';
    return !(status === 'NOT_STARTED' || status === 'FAILED');
  });

  /** Context-appropriate label for the ingest button. */
  protected readonly ingestLabel = computed(() => {
    if (this.ingesting()) {
      return 'Starting…';
    }
    if (this.status()?.state !== 'DOWNLOADED') {
      return 'Download the dataset first';
    }
    const status = this.ingestion()?.status ?? 'NOT_STARTED';
    if (status === 'RUNNING' || status === 'PENDING') {
      return 'Ingestion in progress…';
    }
    if (status === 'COMPLETED') {
      return 'Ingestion complete';
    }
    if (status === 'FAILED') {
      return 'Retry ingestion';
    }
    return 'Ingest into evidence store';
  });

  /** Overall ingestion progress percentage (0–100). */
  protected readonly ingestionPct = computed(() => {
    const i = this.ingestion();
    if (!i || i.records_total <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((i.records_done / i.records_total) * 100));
  });

  private ingestionPollSub: Subscription | null = null;

  private readonly notifications = inject(NotificationService);

  constructor(private readonly adminService: AdminService) {}

  ngOnInit(): void {
    this.load();
    this.loadIngestion();
  }

  ngOnDestroy(): void {
    this.stopPolling();
    this.stopIngestionPolling();
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

  async download(): Promise<void> {
    const size = this.formatBytes(this.status()?.size_bytes ?? 0);
    const ok = await this.notifications.confirm({
      title: 'Start dataset download?',
      message: `This streams the full managed dataset (${size}) from Zenodo through the Airflow acquisition workflow. It is a long-running, bandwidth-heavy operation.`,
      confirmLabel: 'Start download',
    });
    if (!ok) {
      return;
    }

    this.triggering.set(true);
    this.error.set(null);
    this.adminService.triggerDatasetDownload('admin').subscribe({
      next: (response) => {
        this.applyStatus(response);
        this.triggering.set(false);
        this.notifications.success(
          'Download triggered',
          'The acquisition workflow has started; progress will update below.',
        );
      },
      error: () => {
        this.error.set('Unable to trigger the download. Is the Admin-API running on :8002?');
        this.triggering.set(false);
        this.notifications.error(
          'Download failed to start',
          'Could not trigger acquisition. Is the Admin-API running on :8002?',
        );
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

  loadIngestion(): void {
    this.ingestionError.set(null);
    this.adminService.getIngestionStatus().subscribe({
      next: (response) => this.applyIngestion(response),
      error: () => {
        this.ingestionError.set(
          'Unable to load ingestion status. Is the Admin-API running on :8002?',
        );
        this.ingestion.set(null);
        this.stopIngestionPolling();
      },
    });
  }

  async ingest(): Promise<void> {
    const retry = this.ingestion()?.status === 'FAILED';
    const ok = await this.notifications.confirm({
      title: retry ? 'Retry evidence-store ingestion?' : 'Start evidence-store ingestion?',
      message:
        'This batch-ingests the downloaded dataset into the MongoDB evidence store — a long-running restore + normalize job that writes millions of records. A completed run auto-triggers metric computation.',
      confirmLabel: retry ? 'Retry ingestion' : 'Start ingestion',
    });
    if (!ok) {
      return;
    }

    this.ingesting.set(true);
    this.ingestionError.set(null);
    this.adminService.triggerDatasetIngest('admin').subscribe({
      next: (response) => {
        this.applyIngestion(response);
        this.ingesting.set(false);
        this.notifications.success(
          'Ingestion started',
          'The batch-ingestion run is in flight; progress will update below.',
        );
      },
      error: (err: HttpErrorResponse) => {
        if (err.status === 409) {
          this.ingestionError.set('Download the dataset before ingesting into the evidence store.');
          this.notifications.warning(
            'Download required',
            'Download the dataset before ingesting into the evidence store.',
          );
        } else {
          this.ingestionError.set(
            'Unable to start ingestion. Is the Admin-API running on :8002?',
          );
          this.notifications.error(
            'Ingestion failed to start',
            'Could not start the ingestion run. Is the Admin-API running on :8002?',
          );
        }
        this.ingesting.set(false);
      },
    });
  }

  /** Store a fresh ingestion progress and (re)configure polling. */
  private applyIngestion(progress: IngestionProgress): void {
    this.ingestion.set(progress);
    if (progress.status === 'PENDING' || progress.status === 'RUNNING') {
      this.startIngestionPolling();
    } else {
      this.stopIngestionPolling();
    }
  }

  private startIngestionPolling(): void {
    if (this.ingestionPollSub) {
      return;
    }
    this.ingestionPollSub = interval(POLL_INTERVAL_MS)
      .pipe(switchMap(() => this.adminService.getIngestionStatus()))
      .subscribe({
        next: (response) => {
          this.ingestion.set(response);
          if (response.status === 'COMPLETED' || response.status === 'FAILED') {
            this.stopIngestionPolling();
          }
        },
        error: () => {
          this.ingestionError.set(
            'Lost contact with the Admin-API while polling ingestion. Retry with Refresh.',
          );
          this.stopIngestionPolling();
        },
      });
  }

  private stopIngestionPolling(): void {
    this.ingestionPollSub?.unsubscribe();
    this.ingestionPollSub = null;
  }

  /** Percentage complete for a single entity row (0–100). */
  entityPct(done: number, total: number): number {
    if (total <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((done / total) * 100));
  }

  /** CSS modifier for an ingestion status badge. */
  ingestionBadgeClass(status: IngestionStatus | string): string {
    return `badge badge--ing-${String(status).toLowerCase().replace(/_/g, '-')}`;
  }

  /** Human-readable count, e.g. 2.7M. */
  formatCount(value: number): string {
    if (value == null || value <= 0) {
      return '0';
    }
    if (value >= 1_000_000) {
      return `${Math.round((value / 1_000_000) * 10) / 10}M`;
    }
    if (value >= 1_000) {
      return `${Math.round((value / 1_000) * 10) / 10}K`;
    }
    return `${value}`;
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
