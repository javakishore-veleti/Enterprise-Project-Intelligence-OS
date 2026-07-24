import { Routes } from '@angular/router';

import { Dashboard } from './dashboard/dashboard';
import { AgentsList } from './agents-list/agents-list';
import { AuditList } from './audit-list/audit-list';
import { SystemHealth } from './system-health/system-health';
import { DataManagement } from './data-management/data-management';
import { InitialDataset } from './initial-dataset/initial-dataset';
import { Organizations } from './organizations/organizations';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: Dashboard },
  { path: 'agents', component: AgentsList },
  { path: 'organizations', component: Organizations },
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
