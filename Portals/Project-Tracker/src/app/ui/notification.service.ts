import { Injectable, signal } from '@angular/core';

export type ToastKind = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: number;
  kind: ToastKind;
  title: string;
  message?: string;
}

export interface ConfirmRequest {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

interface PendingConfirm {
  req: ConfirmRequest;
  resolve: (value: boolean) => void;
}

/** App-wide toast notifications + a promise-based confirmation dialog. */
@Injectable({ providedIn: 'root' })
export class NotificationService {
  readonly toasts = signal<Toast[]>([]);
  readonly pendingConfirm = signal<PendingConfirm | null>(null);
  private seq = 0;

  private push(kind: ToastKind, title: string, message?: string, timeout = 4500): void {
    const id = ++this.seq;
    this.toasts.update((list) => [...list, { id, kind, title, message }]);
    if (timeout) {
      setTimeout(() => this.dismiss(id), timeout);
    }
  }

  success(title: string, message?: string): void { this.push('success', title, message); }
  info(title: string, message?: string): void { this.push('info', title, message); }
  warning(title: string, message?: string): void { this.push('warning', title, message, 6000); }
  error(title: string, message?: string): void { this.push('error', title, message, 8000); }

  dismiss(id: number): void {
    this.toasts.update((list) => list.filter((t) => t.id !== id));
  }

  /** Open a confirmation dialog; resolves true on confirm, false on cancel. */
  confirm(req: ConfirmRequest): Promise<boolean> {
    return new Promise<boolean>((resolve) => this.pendingConfirm.set({ req, resolve }));
  }

  resolveConfirm(value: boolean): void {
    const pending = this.pendingConfirm();
    if (pending) {
      pending.resolve(value);
      this.pendingConfirm.set(null);
    }
  }
}
