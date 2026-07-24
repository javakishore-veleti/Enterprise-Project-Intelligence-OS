import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { environment } from '../../../environments/environment';
import { OrgTree } from './org-tree';

const base = `${environment.orgApiBaseUrl}/api/v1`;

function org(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
  return {
    org_id: 'r1', parent_org_id: null, root_org_id: 'r1', path: 'r1',
    depth: 0, level: 1, name: 'Acme', kind: 'tenant', status: 'active',
    created_at: '2026-07-19T00:00:00Z', child_count: 0, member_count: 0,
    ...overrides,
  };
}

describe('OrgTree', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OrgTree],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('loads only roots initially (never a subtree)', () => {
    const fixture = TestBed.createComponent(OrgTree);
    fixture.detectChanges();

    const roots = httpMock.expectOne(`${base}/orgs`);
    expect(roots.request.method).toBe('GET');
    roots.flush({ organizations: [org({ child_count: 2 })] });

    fixture.detectChanges();
    const nodes = (fixture.nativeElement as HTMLElement).querySelectorAll('.tree__node');
    expect(nodes.length).toBe(1);
    expect(nodes[0].textContent).toContain('Acme');
    // No subtree call is made for rendering.
    httpMock.expectNone(`${base}/orgs/r1/subtree`);
  });

  it('fetches a node\'s children (paged) when expanded', () => {
    const fixture = TestBed.createComponent(OrgTree);
    fixture.detectChanges();
    httpMock.expectOne(`${base}/orgs`).flush({ organizations: [org({ child_count: 1 })] });
    fixture.detectChanges();

    const component = fixture.componentInstance as unknown as {
      toggle: (o: unknown) => void;
    };
    component.toggle(org({ child_count: 1 }));

    const kids = httpMock.expectOne(
      (r) => r.url === `${base}/orgs/r1/children` && r.params.get('offset') === '0',
    );
    expect(kids.request.method).toBe('GET');
    kids.flush({
      organizations: [org({ org_id: 'c1', parent_org_id: 'r1', path: 'r1.c1', depth: 1, level: 2, name: 'Platform' })],
      total: 1, returned: 1, offset: 0, limit: 25,
    });

    fixture.detectChanges();
    const nodes = (fixture.nativeElement as HTMLElement).querySelectorAll('.tree__node');
    expect(nodes.length).toBe(2);
    expect(nodes[1].textContent).toContain('Platform');
  });
});
