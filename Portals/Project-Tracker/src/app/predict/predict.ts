import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { About } from '../ui/about';

@Component({
  selector: 'app-predict',
  imports: [RouterLink, About],
  template: `
    <div class="stage-top"><app-about title="Predict" text="What happens next — delivery forecasts, release-confidence, and trend projections across the portfolio." /></div>
    <section class="stage">
      <div class="stage__icon">
        <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 14l3-4 3 2 5-7"/><polyline points="17 5 21 5 21 9"/></svg>
      </div>
      <h1>Predict — what happens next</h1>
      <p class="stage__lead">Delivery forecasts, release-confidence, and trend projections across the portfolio.</p>
      <div class="stage__grid">
        <div class="stage__item"><strong>Live today</strong><span>Resolution-velocity trend (recent vs prior window) and metric history power early forecasts on the Decide screen.</span></div>
        <div class="stage__item"><strong>Coming</strong><span>Release success prediction, delivery-slip forecast, and a scenario simulator ("what if we delay Feature A by two weeks?").</span></div>
      </div>
      <a class="stage__cta" routerLink="/decide">See current risk signals in Decide →</a>
    </section>
  `,
  styleUrl: './stage.css',
})
export class Predict {}
