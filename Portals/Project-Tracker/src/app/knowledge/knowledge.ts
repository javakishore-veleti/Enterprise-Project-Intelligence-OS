import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-knowledge',
  imports: [RouterLink],
  template: `
    <section class="stage">
      <div class="stage__icon">
        <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/></svg>
      </div>
      <h1>Knowledge — enterprise memory</h1>
      <p class="stage__lead">The organizational knowledge graph: how teams, projects, systems, dependencies, and past incidents relate.</p>
      <div class="stage__grid">
        <div class="stage__item"><strong>Foundation today</strong><span>Every finding is grounded in evidence and cites the metrics behind it — the raw material for durable enterprise memory.</span></div>
        <div class="stage__item"><strong>Coming</strong><span>Root-cause graph, historical-incident recall, and a searchable knowledge graph across projects and systems.</span></div>
      </div>
      <a class="stage__cta" routerLink="/investigate">Explore the evidence in Investigate →</a>
    </section>
  `,
  styleUrl: '../predict/stage.css',
})
export class Knowledge {}
