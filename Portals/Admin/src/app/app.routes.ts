import { Routes } from '@angular/router';

import { Dashboard } from './dashboard/dashboard';
import { AgentsList } from './agents-list/agents-list';
import { AuditList } from './audit-list/audit-list';
import { SystemHealth } from './system-health/system-health';
import { DataManagement } from './data-management/data-management';
import { InitialDataset } from './initial-dataset/initial-dataset';
import { OrgTree } from './organizations/org-tree/org-tree';
import { OrgDetail } from './organizations/org-detail/org-detail';
import { OrgOverview } from './organizations/org-overview/org-overview';
import { OrgMembers } from './organizations/org-members/org-members';
import { OrgRepositories } from './organizations/org-repositories/org-repositories';
import { OrgAccess } from './organizations/org-access/org-access';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: Dashboard },
  { path: 'agents', component: AgentsList },

  // Organizations: each operation is its own deep-linkable page. The tree page
  // lazy-loads; the per-org detail shell hosts the Overview/Members/Repos/Access
  // sub-pages, each of which loads only its own data on demand.
  { path: 'organizations', component: OrgTree },
  {
    path: 'organizations/:orgId',
    component: OrgDetail,
    children: [
      { path: '', component: OrgOverview },
      { path: 'members', component: OrgMembers },
      { path: 'repositories', component: OrgRepositories },
      { path: 'access', component: OrgAccess },
    ],
  },

  { path: 'audit', component: AuditList },
  { path: 'health', component: SystemHealth },
  {
    path: 'data',
    component: DataManagement,
    children: [
      { path: '', redirectTo: 'initial-dataset', pathMatch: 'full' },
      { path: 'initial-dataset', component: InitialDataset },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
