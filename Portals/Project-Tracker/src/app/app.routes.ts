import { Routes } from '@angular/router';

import { Mission } from './mission/mission';
import { Dashboard } from './dashboard/dashboard';
import { ProjectsList } from './projects-list/projects-list';
import { ProjectGroups } from './project-groups/project-groups';
import { Predict } from './predict/predict';
import { Decide } from './decide/decide';
import { Knowledge } from './knowledge/knowledge';
import { Help } from './help/help';

export const routes: Routes = [
  { path: '', component: Mission },
  { path: 'watch', pathMatch: 'full', redirectTo: 'watch/attention' },
  { path: 'watch/:view', component: Dashboard },
  { path: 'investigate', pathMatch: 'full', redirectTo: 'investigate/new' },
  { path: 'investigate/:view', component: ProjectsList },
  { path: 'groups', component: ProjectGroups },
  { path: 'predict', pathMatch: 'full', redirectTo: 'predict/forecasts' },
  { path: 'predict/:view', component: Predict },
  { path: 'decide', pathMatch: 'full', redirectTo: 'decide/options' },
  { path: 'decide/:view', component: Decide },
  { path: 'knowledge', component: Knowledge },
  { path: 'help', pathMatch: 'full', redirectTo: 'help/mission' },
  { path: 'help/:view', component: Help },
  // Back-compat redirects from the old entity-based routes.
  { path: 'projects', redirectTo: 'investigate' },
  { path: 'risk', redirectTo: 'decide' },
  { path: '**', redirectTo: '' },
];
