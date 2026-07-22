import { Component, NgZone, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription, timer } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { DashboardActivity } from '../models/analysis';
import { RiskAnalyticsService } from '../services/risk-analytics.service';

const POLL_MS = 20000;

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit, OnDestroy {
  private readonly riskService = inject(RiskAnalyticsService);
  private readonly zone = inject(NgZone);

  protected readonly activity = signal<DashboardActivity | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly refreshing = signal(false);

  private sub?: Subscription;

  protected readonly runs = computed(() => this.activity()?.recent_runs ?? []);
  protected readonly findings = computed(() => this.activity()?.recent_findings ?? []);
  protected readonly totals = computed(
    () => this.activity()?.totals ?? { total_runs: 0, total_findings: 0, projects_analyzed: 0 },
  );
  protected readonly highSeverity = computed(
    () => this.findings().filter((f) => ['HIGH', 'CRITICAL'].includes((f.severity || '').toUpperCase())).length,
  );

  /** Distribution of recent findings by severity — drives the stacked bar. */
  protected readonly severityMix = computed(() => {
    const keys = ['critical', 'high', 'medium', 'low'] as const;
    const counts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const f of this.findings()) {
      const s = (f.severity || '').toLowerCase();
      if (s in counts) counts[s] += 1;
    }
    const total = keys.reduce((n, k) => n + counts[k], 0);
    const segments = keys.map((k) => ({
      key: k,
      label: k.charAt(0).toUpperCase() + k.slice(1),
      count: counts[k],
      pct: total ? (counts[k] / total) * 100 : 0,
    }));
    return { segments, total };
  });

  ngOnInit(): void {
    // Poll immediately, then every POLL_MS. Run the recurring timer OUTSIDE
    // Angular's zone so it doesn't keep the app perpetually unstable; hop back
    // into the zone only to apply signal updates.
    this.zone.runOutsideAngular(() => {
      this.sub = timer(0, POLL_MS)
        .pipe(switchMap(() => {
          this.zone.run(() => this.refreshing.set(true));
          return this.riskService.getActivity(15);
        }))
        .subscribe({
          next: (data) => this.zone.run(() => {
            this.activity.set(data);
            this.loading.set(false);
            this.refreshing.set(false);
            this.error.set(null);
          }),
          error: () => this.zone.run(() => {
            this.loading.set(false);
            this.refreshing.set(false);
            this.error.set('Unable to load live activity. Is the RiskAnalytics-API running on :8004?');
          }),
        });
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  protected severityClass(severity: string): string {
    return (severity || 'unknown').toLowerCase();
  }

  protected statusClass(status: string): string {
    return (status || '').toLowerCase();
  }

  /** "3m ago" style relative time from an ISO timestamp. */
  protected ago(iso: string | null): string {
    if (!iso) return '—';
    const then = new Date(iso).getTime();
    const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (secs < 60) return `${secs}s ago`;
    const mins = Math.round(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.round(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.round(hrs / 24)}d ago`;
  }
}
