import { Routes } from '@angular/router';

import { ProjectsList } from './projects-list/projects-list';
import { ProjectRisk } from './project-risk/project-risk';

export const routes: Routes = [
  { path: '', component: ProjectsList },
  { path: 'risk', component: ProjectRisk },
  { path: '**', redirectTo: '' },
];
