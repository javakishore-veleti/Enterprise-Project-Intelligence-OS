import { DecimalPipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AttentionItem } from '../models/analysis';
import { RiskAnalyticsService } from '../services/risk-analytics.service';

const SEVERITY_RANK: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
const FETCH = 100; // server returns top-100 by attention; we sort/slice client-side

type SortKey = 'priority' | 'slip' | 'severity' | 'confidence' | 'recent' | 'project';

/** Watch = the Signals & Attention workbench (cards/table, sortable, top-N, date history). */
@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, FormsModule, DecimalPipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {
  private readonly risk = inject(RiskAnalyticsService);

  private readonly all = signal<AttentionItem[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  // View controls.
  protected view: 'cards' | 'table' = 'cards';
  protected sortBy: SortKey = 'priority';
  protected topN = 10;
  protected asOf = '';

  protected readonly sorts: ReadonlyArray<{ key: SortKey; label: string }> = [
    { key: 'priority', label: 'AI priority (smart)' },
    { key: 'slip', label: 'Slip likelihood' },
    { key: 'severity', label: 'Severity' },
    { key: 'confidence', label: 'AI confidence' },
    { key: 'recent', label: 'Most recent' },
    { key: 'project', label: 'Project' },
  ];
  protected readonly topOptions = [5, 10, 25, 50, 100];
  protected readonly todayStr = this.isoDate(0);

  /** Sorted then sliced to top-N — the displayed set. */
  protected readonly items = computed(() => {
    const sorted = [...this.all()].sort((a, b) => this.cmp(a, b));
    return sorted.slice(0, this.topN);
  });

  ngOnInit(): void {
    this.reload();
  }

  /** Only date/scope change requires a refetch; sort + top-N + view are client-side. */
  protected onDateChange(): void { this.reload(); }
  protected setToday(): void { this.asOf = ''; this.reload(); }
  protected setYesterday(): void { this.asOf = this.isoDate(-1); this.reload(); }
  protected get isToday(): boolean { return this.asOf === '' || this.asOf === this.todayStr; }

  private reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.risk.getAttention(FETCH, { asOf: this.asOf || undefined }).subscribe({
      next: (r) => { this.all.set(r.items); this.total.set(r.total); this.loading.set(false); },
      error: () => {
        this.error.set('Unable to load the attention feed. Is the RiskAnalytics-API running on :8004?');
        this.loading.set(false);
      },
    });
  }

  private cmp(a: AttentionItem, b: AttentionItem): number {
    switch (this.sortBy) {
      case 'slip': return (b.probability ?? 0) - (a.probability ?? 0);
      case 'confidence': return (b.confidence ?? 0) - (a.confidence ?? 0);
      case 'severity':
        return (SEVERITY_RANK[(b.severity || '').toUpperCase()] ?? 0) - (SEVERITY_RANK[(a.severity || '').toUpperCase()] ?? 0)
          || b.attention_score - a.attention_score;
      case 'recent': return new Date(b.analysis_timestamp).getTime() - new Date(a.analysis_timestamp).getTime();
      case 'project': return a.project_key.localeCompare(b.project_key);
      default: return b.attention_score - a.attention_score;
    }
  }

  protected severityClass(sev: string): string { return (sev || 'unknown').toLowerCase(); }
  protected pctOf(v: number): number { return Math.round((v ?? 0) * 100); }
  protected primaryAction(a: AttentionItem): string | null { return a.recommended_actions?.[0] ?? null; }
  protected ago(iso: string): string {
    const then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    const s = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (s < 60) return `${s}s ago`;
    const m = Math.round(s / 60); if (m < 60) return `${m}m ago`;
    const h = Math.round(m / 60); if (h < 24) return `${h}h ago`;
    return `${Math.round(h / 24)}d ago`;
  }

  private isoDate(days: number): string {
    const d = new Date(); d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  }
}
