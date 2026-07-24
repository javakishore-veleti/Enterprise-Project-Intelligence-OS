import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { AgentConfig, AuditEvent } from '../models/admin';
import { Organization } from '../models/org';
import { AdminService } from '../services/admin.service';
import { OrgAdminService } from '../services/org-admin.service';

/** A tenant root plus the size of its subtree (for the org summary). */
interface RootSummary {
  org: Organization;
  nodeCount: number;
}

/**
 * Admin Console home. Summarizes three things at a glance from real data:
 *  - Organizations (Org-Management-API, :8005)
 *  - Configured agents (Admin-API, :8002)
 *  - Agent status + recent platform activity (Admin-API audit — the Admin
 *    portal has no dedicated agent-run feed, so this reflects current agent
 *    enabled/framework status alongside real audited config activity).
 */
@Component({
  selector: 'app-dashboard',
  imports: [RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly orgAdmin = inject(OrgAdminService);

  // --- Organizations --------------------------------------------------------
  protected readonly orgCount = signal(0);
  protected readonly roots = signal<RootSummary[]>([]);
  protected readonly orgsLoading = signal(true);
  protected readonly orgsError = signal<string | null>(null);

  protected readonly rootCount = computed(() => this.roots().length);

  // --- Agents ---------------------------------------------------------------
  protected readonly agents = signal<AgentConfig[]>([]);
  protected readonly agentsLoading = signal(true);
  protected readonly agentsError = signal<string | null>(null);

  protected readonly agentCount = computed(() => this.agents().length);
  protected readonly enabledAgentCount = computed(
    () => this.agents().filter((a) => a.enabled).length,
  );
  protected readonly disabledAgentCount = computed(
    () => this.agents().filter((a) => !a.enabled).length,
  );
  /** Framework -> number of agents using it (real breakdown). */
  protected readonly frameworkBreakdown = computed(() => {
    const counts = new Map<string, number>();
    for (const a of this.agents()) {
      counts.set(a.framework, (counts.get(a.framework) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([framework, count]) => ({ framework, count }))
      .sort((a, b) => b.count - a.count);
  });

  // --- Recent activity (audit as the executions/activity feed) --------------
  protected readonly activity = signal<AuditEvent[]>([]);
  protected readonly activityLoading = signal(true);
  protected readonly activityError = signal<string | null>(null);

  ngOnInit(): void {
    this.loadOrganizations();
    this.loadAgents();
    this.loadActivity();
  }

  loadOrganizations(): void {
    this.orgsLoading.set(true);
    this.orgsError.set(null);
    this.orgAdmin.listRoots().subscribe({
      next: (resp) => {
        const rootOrgs = resp.organizations;
        if (rootOrgs.length === 0) {
          this.roots.set([]);
          this.orgCount.set(0);
          this.orgsLoading.set(false);
          return;
        }
        forkJoin(rootOrgs.map((r) => this.orgAdmin.subtree(r.org_id))).subscribe({
          next: (subtrees) => {
            const unique = new Set<string>();
            const summaries: RootSummary[] = rootOrgs.map((r, i) => {
              const nodes = subtrees[i].organizations;
              for (const o of nodes) {
                unique.add(o.org_id);
              }
              return { org: r, nodeCount: nodes.length };
            });
            this.roots.set(summaries);
            this.orgCount.set(unique.size);
            this.orgsLoading.set(false);
          },
          error: () => this.failOrgs(),
        });
      },
      error: () => this.failOrgs(),
    });
  }

  private failOrgs(): void {
    this.orgsError.set('Unable to reach the Org-Management-API on :8005.');
    this.roots.set([]);
    this.orgCount.set(0);
    this.orgsLoading.set(false);
  }

  loadAgents(): void {
    this.agentsLoading.set(true);
    this.agentsError.set(null);
    this.adminService.listAgents({ limit: 200, offset: 0 }).subscribe({
      next: (resp) => {
        this.agents.set(resp.items);
        this.agentsLoading.set(false);
      },
      error: () => {
        this.agentsError.set('Unable to reach the Admin-API on :8002.');
        this.agents.set([]);
        this.agentsLoading.set(false);
      },
    });
  }

  loadActivity(): void {
    this.activityLoading.set(true);
    this.activityError.set(null);
    this.adminService.getAudit({ limit: 8, offset: 0 }).subscribe({
      next: (resp) => {
        this.activity.set(resp.items);
        this.activityLoading.set(false);
      },
      error: () => {
        this.activityError.set('Unable to load recent activity from the Admin-API on :8002.');
        this.activity.set([]);
        this.activityLoading.set(false);
      },
    });
  }

  refresh(): void {
    this.loadOrganizations();
    this.loadAgents();
    this.loadActivity();
  }
}
