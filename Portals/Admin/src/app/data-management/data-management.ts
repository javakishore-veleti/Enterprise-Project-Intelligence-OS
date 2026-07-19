import { Component } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

/**
 * Shell for the Data Management area: a left sub-nav (sidebar) plus a
 * router-outlet for its child views. Designed so more items can be added
 * alongside "Initial Dataset" later.
 */
@Component({
  selector: 'app-data-management',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './data-management.html',
  styleUrl: './data-management.css',
})
export class DataManagement {}
