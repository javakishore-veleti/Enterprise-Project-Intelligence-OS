import { Component, Input } from '@angular/core';

/** A small "About this page" banner shown at the top of each page. */
@Component({
  selector: 'app-about',
  template: `
    <div class="about">
      <span class="about__icon">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><line x1="12" y1="11" x2="12" y2="16.5"/><line x1="12" y1="7.5" x2="12.01" y2="7.5"/></svg>
      </span>
      <p class="about__text"><b>About {{ title }}</b> — {{ text }}</p>
    </div>
  `,
  styles: [`
    .about {
      display: flex; align-items: flex-start; gap: .7rem;
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 12px; padding: .9rem 1.1rem; margin-bottom: 1.4rem;
    }
    .about__icon { color: #d97706; flex: none; margin-top: .15rem; }
    .about__icon svg { width: 20px; height: 20px; }
    .about__text { margin: 0; font-size: 1rem; color: #111827; line-height: 1.5; }
    .about__text b { color: #92400e; font-weight: 800; }
  `],
})
export class About {
  @Input() title = '';
  @Input() text = '';
}
