import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs/operators';
import { NotificationService } from './ui/notification.service';

// Page title MUST match the sidebar menu label so the breadcrumb and the active
// nav item always read the same word (Admin Console > Agents / System Health / …).
const PAGE_TITLES: Record<string, { title: string; crumb: string }> = {
  '/dashboard': { title: 'Dashboard', crumb: 'Dashboard' },
  '/agents': { title: 'Agents', crumb: 'Agents' },
  '/organizations': { title: 'Organizations', crumb: 'Organizations' },
  '/audit': { title: 'Audit', crumb: 'Audit' },
  '/health': { title: 'System Health', crumb: 'System Health' },
  '/data': { title: 'Data Management', crumb: 'Data Management' },
  '/data/initial-dataset': { title: 'Initial Dataset', crumb: 'Initial Dataset' },
};

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly notifications = inject(NotificationService);
  private readonly router = inject(Router);

  protected readonly toasts = this.notifications.toasts;
  protected readonly confirm = this.notifications.pendingConfirm;
  protected readonly navOpen = signal(true);
  protected readonly pageTitle = signal('Dashboard');
  protected readonly pageCrumb = signal('Dashboard');
  /** Whether the Organizations parent nav item is expanded to show its sub-nav. */
  protected readonly orgNavExpanded = signal(false);

  protected readonly today = new Date().toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric',
  });

  constructor() {
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => {
        const path = e.urlAfterRedirects.split('?')[0].split('#')[0];
        const meta = PAGE_TITLES[path] ?? PAGE_TITLES['/dashboard'];
        this.pageTitle.set(meta.title);
        this.pageCrumb.set(meta.crumb);
        // Auto-expand the Organizations sub-nav whenever an org view is active.
        if (path.startsWith('/organizations')) {
          this.orgNavExpanded.set(true);
        }
      });
  }

  protected toggleNav(): void {
    this.navOpen.update((v) => !v);
  }

  protected toggleOrgNav(): void {
    this.orgNavExpanded.update((v) => !v);
  }

  protected toastIcon(kind: string): string {
    return kind === 'success' ? '✓' : kind === 'error' ? '!' : kind === 'warning' ? '⚠' : 'i';
  }
}
