import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { map } from 'rxjs/operators';

import { About } from '../ui/about';

/**
 * Help = per-verb explainer pages. Today it hosts the Predict-vs-Decide
 * differentiation (both topics show the same comparison for now); each verb
 * gets its own entry so the sidebar sub-nav mirrors the product's verb IA.
 */
@Component({
  selector: 'app-help',
  imports: [RouterLink, About],
  templateUrl: './help.html',
  styleUrl: './help.css',
})
export class Help {
  private readonly route = inject(ActivatedRoute);

  /** Which verb's help page (?v=predict|decide). Same content for now. */
  protected readonly topic = toSignal(
    this.route.queryParamMap.pipe(map((p) => (p.get('v') === 'decide' ? 'decide' : 'predict'))),
    { initialValue: 'predict' as 'predict' | 'decide' },
  );

  protected readonly heading = computed(() =>
    this.topic() === 'decide' ? 'Help · Decide' : 'Help · Predict',
  );

  /** The Predict-vs-Decide comparison, row by row. */
  protected readonly rows = [
    { dim: 'Question', predict: '“What will happen?”', decide: '“What should we do?”' },
    { dim: 'Output', predict: 'A forecast / projection — outcome + credible interval + drivers', decide: 'A plan / decision — prioritized actions, owners, options' },
    { dim: 'Stance', predict: 'Descriptive, exploratory — no commitment', decide: 'Prescriptive, committed — approve & act' },
    { dim: 'Scenario handling', predict: 'Digital-Twin what-if: “IF you did X → predicted future state + cascade + uncertainty” (a sandbox)', decide: 'Decision options: “Here are the recommended actions, trade-offs — pick one and I’ll execute it” (a proposal)' },
    { dim: 'Grounded in', predict: 'Trajectory / metric-history forecasting', decide: 'Interventions / mitigations (which lever to pull)' },
    { dim: 'Ends with', predict: 'A confidence-scored prediction you review', decide: 'A ticket created / owner assigned (with approval)' },
  ];
}
