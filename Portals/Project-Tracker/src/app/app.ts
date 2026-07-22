import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs/operators';
import { NotificationService } from './ui/notification.service';
import { ScopeSwitcher } from './ui/scope-switcher';

// Page title MUST match the sidebar menu label so the breadcrumb and the active
// nav item always read the same word (Project Tracker > Projects / Project Risk).
const PAGE_TITLES: Record<string, { title: string; crumb: string }> = {
  '/': { title: 'Mission', crumb: 'Mission' },
  '/watch': { title: 'Watch', crumb: 'Watch' },
  '/investigate': { title: 'Investigate', crumb: 'Investigate' },
  '/groups': { title: 'Project Groups', crumb: 'Investigate' },
  '/predict': { title: 'Predict', crumb: 'Predict' },
  '/decide': { title: 'Decide', crumb: 'Decide' },
  '/knowledge': { title: 'Knowledge', crumb: 'Knowledge' },
};

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ScopeSwitcher],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly notifications = inject(NotificationService);
  private readonly router = inject(Router);

  protected readonly toasts = this.notifications.toasts;
  protected readonly confirm = this.notifications.pendingConfirm;
  protected readonly navOpen = signal(true);
  protected readonly pageTitle = signal('Portfolio Overview');
  protected readonly pageCrumb = signal('Projects');
  protected readonly onWatch = signal(false);
  protected readonly onInvestigate = signal(false);

  protected readonly today = new Date().toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric',
  });

  constructor() {
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => {
        const path = e.urlAfterRedirects.split('?')[0];
        this.onWatch.set(path === '/watch');
        this.onInvestigate.set(path === '/investigate');
        const meta = PAGE_TITLES[path] ?? PAGE_TITLES['/'];
        this.pageTitle.set(meta.title);
        this.pageCrumb.set(meta.crumb);
      });
  }

  protected toggleNav(): void {
    this.navOpen.update((v) => !v);
  }
}
