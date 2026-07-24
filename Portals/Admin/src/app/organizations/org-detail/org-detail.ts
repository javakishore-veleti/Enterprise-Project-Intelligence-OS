import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { Organization } from '../../models/org';
import { OrgAdminService } from '../../services/org-admin.service';

/**
 * Shell for the per-org detail pages (route: /organizations/:orgId). Renders a
 * breadcrumb (Organizations / <org>) plus tabs to the Overview / Members /
 * Repositories / Access sub-pages, and hosts them in a child <router-outlet>.
 * Each sub-page loads only its own data on demand.
 */
@Component({
  selector: 'app-org-detail',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './org-detail.html',
  styleUrls: ['../org.css'],
})
export class OrgDetail implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly orgAdmin = inject(OrgAdminService);

  protected readonly orgId = signal<string>('');
  protected readonly org = signal<Organization | null>(null);

  ngOnInit(): void {
    this.route.paramMap.subscribe((pm) => {
      const id = pm.get('orgId') ?? '';
      this.orgId.set(id);
      if (id) {
        this.orgAdmin.getOrg(id).subscribe({
          next: (o) => this.org.set(o),
          error: () => this.org.set(null),
        });
      }
    });
  }
}
