import { Routes } from '@angular/router';

import { AgentsList } from './agents-list/agents-list';
import { AuditList } from './audit-list/audit-list';
import { SystemHealth } from './system-health/system-health';

export const routes: Routes = [
  { path: '', redirectTo: 'agents', pathMatch: 'full' },
  { path: 'agents', component: AgentsList },
  { path: 'audit', component: AuditList },
  { path: 'health', component: SystemHealth },
  { path: '**', redirectTo: 'agents' },
];
