import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { NotificationService } from './ui/notification.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly notifications = inject(NotificationService);
  protected readonly toasts = this.notifications.toasts;
  protected readonly confirm = this.notifications.pendingConfirm;
  protected readonly navOpen = signal(true);

  protected readonly today = new Date().toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric',
  });

  protected toggleNav(): void {
    this.navOpen.update((v) => !v);
  }

  protected toastIcon(kind: string): string {
    return kind === 'success' ? '✓' : kind === 'error' ? '!' : kind === 'warning' ? '⚠' : 'i';
  }
}
