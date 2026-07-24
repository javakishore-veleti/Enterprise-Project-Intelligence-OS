import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { environment } from '../../environments/environment';
import { OrgContextService } from './org-context.service';

/**
 * Stamps `X-Org-Key: <org id>` onto every outbound request to the data APIs
 * (Projects-API :8003 + RiskAnalytics-API :8004) whenever an org is selected,
 * so the backend re-scopes to that org's visible projects. Requests to the
 * Org-Management-API itself are never scoped (it resolves the tree). When no
 * org is selected the request is passed through unchanged (unscoped).
 */
export const orgScopeInterceptor: HttpInterceptorFn = (req, next) => {
  const orgId = inject(OrgContextService).currentOrgId();
  if (!orgId) {
    return next(req);
  }
  const scoped =
    req.url.startsWith(environment.apiBaseUrl) || req.url.startsWith(environment.riskApiBaseUrl);
  if (!scoped) {
    return next(req);
  }
  return next(req.clone({ setHeaders: { 'X-Org-Key': orgId } }));
};
