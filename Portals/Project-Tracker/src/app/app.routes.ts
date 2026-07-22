import { Routes } from '@angular/router';

import { Dashboard } from './dashboard/dashboard';
import { ProjectsList } from './projects-list/projects-list';
import { ProjectGroups } from './project-groups/project-groups';
import { ProjectRisk } from './project-risk/project-risk';

export const routes: Routes = [
  { path: '', component: Dashboard },
  { path: 'projects', component: ProjectsList },
  { path: 'groups', component: ProjectGroups },
  { path: 'risk', component: ProjectRisk },
  { path: '**', redirectTo: '' },
];
