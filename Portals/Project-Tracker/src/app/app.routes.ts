import { Routes } from '@angular/router';

import { ProjectsList } from './projects-list/projects-list';

export const routes: Routes = [
  { path: '', component: ProjectsList },
  { path: '**', redirectTo: '' },
];
