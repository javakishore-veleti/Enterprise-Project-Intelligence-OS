import { Routes } from '@angular/router';

import { Dashboard } from './dashboard/dashboard';
import { AgentsList } from './agents-list/agents-list';
import { AuditList } from './audit-list/audit-list';
import { SystemHealth } from './system-health/system-health';
import { DataManagement } from './data-management/data-management';
import { InitialDataset } from './initial-dataset/initial-dataset';
import { OrgLanding } from './organizations/org-landing/org-landing';
import { OrgProfile } from './organizations/org-profile/org-profile';
import { OrgSubOrgs } from './organizations/org-sub-orgs/org-sub-orgs';
import { OrgMembers } from './organizations/org-members/org-members';
import { OrgRepositories } from './organizations/org-repositories/org-repositories';
import { OrgAccess } from './organizations/org-access/org-access';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: Dashboard },
  { path: 'agents', component: AgentsList },

  // Organizations: a landing picker plus five standalone full-width pages, all
  // driven by one shared selected-org context (OrgContextService). No org id in
  // the URL — the pages read the context and each carries an org picker bar.
  { path: 'organizations', component: OrgLanding },
  { path: 'organizations/profile', component: OrgProfile },
  { path: 'organizations/sub-orgs', component: OrgSubOrgs },
  { path: 'organizations/members', component: OrgMembers },
  { path: 'organizations/repositories', component: OrgRepositories },
  { path: 'organizations/access', component: OrgAccess },

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
