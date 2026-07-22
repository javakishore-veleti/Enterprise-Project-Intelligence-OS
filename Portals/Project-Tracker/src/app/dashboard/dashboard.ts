import { DecimalPipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AttentionItem } from '../models/analysis';
import { RiskAnalyticsService } from '../services/risk-analytics.service';

const PAGE = 20;

/** Watch = the full Signals & Attention stream (the "View all attention" target). */
@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, FormsModule, DecimalPipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {
  private readonly risk = inject(RiskAnalyticsService);

  protected readonly items = signal<AttentionItem[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly loadingMore = signal(false);
  protected readonly error = signal<string | null>(null);

  /** as_of date (YYYY-MM-DD); '' = today (live). */
  protected asOf = '';
  protected readonly todayStr = this.isoDate(0);
  protected offset = 0;

  ngOnInit(): void {
    this.reload();
  }

  protected onDateChange(): void {
    this.reload();
  }

  protected setToday(): void { this.asOf = ''; this.reload(); }
  protected setYesterday(): void { this.asOf = this.isoDate(-1); this.reload(); }

  protected get isToday(): boolean { return this.asOf === '' || this.asOf === this.todayStr; }

  private reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.offset = 0;
    this.risk.getAttention(PAGE, { asOf: this.asOf || undefined, offset: 0 }).subscribe({
      next: (r) => {
        this.items.set(r.items);
        this.total.set(r.total);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load the attention feed. Is the RiskAnalytics-API running on :8004?');
        this.loading.set(false);
      },
    });
  }

  protected loadMore(): void {
    if (this.loadingMore()) return;
    this.loadingMore.set(true);
    this.offset += PAGE;
    this.risk.getAttention(PAGE, { asOf: this.asOf || undefined, offset: this.offset }).subscribe({
      next: (r) => {
        this.items.update((cur) => [...cur, ...r.items]);
        this.total.set(r.total);
        this.loadingMore.set(false);
      },
      error: () => this.loadingMore.set(false),
    });
  }

  protected severityClass(sev: string): string {
    return (sev || 'unknown').toLowerCase();
  }
  protected pctOf(v: number): number {
    return Math.round((v ?? 0) * 100);
  }
  protected primaryAction(a: AttentionItem): string | null {
    return a.recommended_actions?.[0] ?? null;
  }
  protected ago(iso: string): string {
    const then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (secs < 60) return `${secs}s ago`;
    const m = Math.round(secs / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.round(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.round(h / 24)}d ago`;
  }

  /** ISO date string offset by `days` from today (browser-local). */
  private isoDate(days: number): string {
    const d = new Date();
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  }
}
