import { Routes } from '@angular/router';

import { AgentsList } from './agents-list/agents-list';
import { AuditList } from './audit-list/audit-list';
import { SystemHealth } from './system-health/system-health';
import { DataManagement } from './data-management/data-management';
import { InitialDataset } from './initial-dataset/initial-dataset';

export const routes: Routes = [
  { path: '', redirectTo: 'agents', pathMatch: 'full' },
  { path: 'agents', component: AgentsList },
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
  { path: '**', redirectTo: 'agents' },
];
