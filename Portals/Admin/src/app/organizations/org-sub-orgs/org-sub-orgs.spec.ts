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

  it('renders ONLY the current page of children (bounded DOM) — never a subtree', () => {
    ctx.select(org({ child_count: 1 }));
    const fixture = TestBed.createComponent(OrgSubOrgs);
    fixture.detectChanges();

    const kids = httpMock.expectOne(
      (r) =>
        r.url === `${base}/orgs/r1/children` &&
        r.params.get('offset') === '0' &&
        r.params.get('limit') === '25' &&
        r.params.get('sort') === 'name',
    );
    expect(kids.request.method).toBe('GET');
    kids.flush({
      organizations: [org({ org_id: 'c1', parent_org_id: 'r1', path: 'r1.c1', depth: 1, level: 2, name: 'Platform', child_count: 0 })],
      total: 1, returned: 1, offset: 0, limit: 25,
    });

    fixture.detectChanges();
    // Rows render in a compact table — the DOM is bounded to the current page.
    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('tbody tr');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('Platform');
    httpMock.expectNone(`${base}/orgs/r1/subtree`);
  });

  it('page-replaces (does not accumulate) when advancing to the next page', () => {
    ctx.select(org({ child_count: 60 }));
    const fixture = TestBed.createComponent(OrgSubOrgs);
    fixture.detectChanges();

    const p0 = httpMock.expectOne(
      (r) => r.url === `${base}/orgs/r1/children` && r.params.get('offset') === '0',
    );
    p0.flush({
      organizations: Array.from({ length: 25 }, (_, i) =>
        org({ org_id: `a${i}`, parent_org_id: 'r1', name: `A${i}`, child_count: 0 })),
      total: 60, returned: 25, offset: 0, limit: 25,
    });
    fixture.detectChanges();
    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelectorAll('tbody tr').length).toBe(25);

    // Next page fetches offset=25 and REPLACES the rows (still 25, not 50).
    host.querySelectorAll('button').forEach((b) => {
      if (b.textContent?.trim() === 'Next') { (b as HTMLButtonElement).click(); }
    });
    const p1 = httpMock.expectOne(
      (r) => r.url === `${base}/orgs/r1/children` && r.params.get('offset') === '25',
    );
    p1.flush({
      organizations: Array.from({ length: 25 }, (_, i) =>
        org({ org_id: `b${i}`, parent_org_id: 'r1', name: `B${i}`, child_count: 0 })),
      total: 60, returned: 25, offset: 25, limit: 25,
    });
    fixture.detectChanges();
    const rows = host.querySelectorAll('tbody tr');
    expect(rows.length).toBe(25);
    expect(host.textContent).toContain('B0');
    expect(host.textContent).not.toContain('A0');
  });
});
