import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AgentConfig, AuditEvent } from '../models/admin';
import { Organization } from '../models/org';
import { AdminService } from '../services/admin.service';
import { OrgAdminService } from '../services/org-admin.service';

/** How many tenant roots to show in the bounded mini list. */
const MAX_ROOTS_SHOWN = 6;

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
  // Counts come from the cheap COUNT-only stats endpoint (never a subtree
  // fetch); the mini list shows a BOUNDED set of tenant roots from listRoots
  // (already bounded), each with its own cheap child_count.
  protected readonly orgCount = signal(0);
  protected readonly rootCount = signal(0);
  protected readonly roots = signal<Organization[]>([]);
  protected readonly orgsLoading = signal(true);
  protected readonly orgsError = signal<string | null>(null);

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
    // 1) Cheap aggregate counts (COUNT queries only — no subtree load).
    this.orgAdmin.orgStats().subscribe({
      next: (stats) => {
        this.orgCount.set(stats.total_orgs);
        this.rootCount.set(stats.root_count);
        this.orgsLoading.set(false);
      },
      error: () => this.failOrgs(),
    });
    // 2) A BOUNDED mini list of tenant roots (listRoots is already bounded;
    //    we cap what we render). Each root carries its own cheap child_count.
    this.orgAdmin.listRoots().subscribe({
      next: (resp) => this.roots.set(resp.organizations.slice(0, MAX_ROOTS_SHOWN)),
      error: () => this.roots.set([]),
    });
  }

  private failOrgs(): void {
    this.orgsError.set('Unable to reach the Org-Management-API on :8005.');
    this.roots.set([]);
    this.orgCount.set(0);
    this.rootCount.set(0);
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
