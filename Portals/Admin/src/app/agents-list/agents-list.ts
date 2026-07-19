import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AGENT_FRAMEWORKS, AgentConfig, AgentFramework } from '../models/admin';
import { AdminService } from '../services/admin.service';

/** Local editable copy of an agent row plus its per-row save state. */
interface AgentRow {
  config: AgentConfig;
  enabled: boolean;
  model: string;
  framework: AgentFramework;
  saving: boolean;
  saved: boolean;
  error: string | null;
}

@Component({
  selector: 'app-agents-list',
  imports: [FormsModule],
  templateUrl: './agents-list.html',
  styleUrl: './agents-list.css',
})
export class AgentsList implements OnInit {
  protected readonly rows = signal<AgentRow[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly frameworks = AGENT_FRAMEWORKS;

  constructor(private readonly adminService: AdminService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.adminService.listAgents({ limit: 200, offset: 0 }).subscribe({
      next: (response) => {
        this.rows.set(response.items.map((config) => this.toRow(config)));
        this.total.set(response.page.total);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to load agents. Is the Admin-API running on :8002?');
        this.rows.set([]);
        this.total.set(0);
        this.loading.set(false);
      },
    });
  }

  private toRow(config: AgentConfig): AgentRow {
    return {
      config,
      enabled: config.enabled,
      model: config.model,
      framework: config.framework,
      saving: false,
      saved: false,
      error: null,
    };
  }

  isDirty(row: AgentRow): boolean {
    return (
      row.enabled !== row.config.enabled ||
      row.model !== row.config.model ||
      row.framework !== row.config.framework
    );
  }

  save(row: AgentRow): void {
    row.saving = true;
    row.saved = false;
    row.error = null;
    this.rows.set([...this.rows()]);

    this.adminService
      .upsertAgent(row.config.agent_key, {
        enabled: row.enabled,
        model: row.model.trim(),
        framework: row.framework,
        prompt_ref: row.config.prompt_ref,
        updated_by: 'admin',
      })
      .subscribe({
        next: (updated) => {
          row.config = updated;
          row.enabled = updated.enabled;
          row.model = updated.model;
          row.framework = updated.framework;
          row.saving = false;
          row.saved = true;
          this.rows.set([...this.rows()]);
        },
        error: () => {
          row.saving = false;
          row.error = 'Save failed.';
          this.rows.set([...this.rows()]);
        },
      });
  }
}
