import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../../environments/environment';
import { Organization } from '../../models/org';
import { OrgContextService } from '../../services/org-context.service';
import { OrgSubOrgs } from './org-sub-orgs';

const base = `${environment.orgApiBaseUrl}/api/v1`;

function org(overrides: Partial<Organization> = {}): Organization {
  return {
    org_id: 'r1', parent_org_id: null, root_org_id: 'r1', path: 'r1',
    depth: 0, level: 1, name: 'Acme', kind: 'tenant', status: 'active',
    created_at: '2026-07-19T00:00:00Z', child_count: 2, member_count: 0,
    ...overrides,
  };
}

describe('OrgSubOrgs', () => {
  let httpMock: HttpTestingController;
  let ctx: OrgContextService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OrgSubOrgs],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    ctx = TestBed.inject(OrgContextService);
  });

  afterEach(() => httpMock.verify());

  it('loads the selected org\'s children (paged) — never a subtree', () => {
    ctx.select(org({ child_count: 1 }));
    const fixture = TestBed.createComponent(OrgSubOrgs);
    fixture.detectChanges();

    const kids = httpMock.expectOne(
      (r) => r.url === `${base}/orgs/r1/children` && r.params.get('offset') === '0',
    );
    expect(kids.request.method).toBe('GET');
    kids.flush({
      organizations: [org({ org_id: 'c1', parent_org_id: 'r1', path: 'r1.c1', depth: 1, level: 2, name: 'Platform', child_count: 0 })],
      total: 1, returned: 1, offset: 0, limit: 25,
    });

    fixture.detectChanges();
    const nodes = (fixture.nativeElement as HTMLElement).querySelectorAll('.tree__node');
    expect(nodes.length).toBe(1);
    expect(nodes[0].textContent).toContain('Platform');
    httpMock.expectNone(`${base}/orgs/r1/subtree`);
  });
});
