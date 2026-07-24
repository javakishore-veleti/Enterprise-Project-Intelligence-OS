import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { Organizations } from './organizations';

const base = `${environment.orgApiBaseUrl}/api/v1`;

describe('Organizations', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Organizations],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('loads roots then merges their subtrees into the tree', () => {
    const fixture = TestBed.createComponent(Organizations);
    fixture.detectChanges();

    const roots = httpMock.expectOne(`${base}/orgs`);
    expect(roots.request.method).toBe('GET');
    roots.flush({
      organizations: [
        {
          org_id: 'r1', parent_org_id: null, root_org_id: 'r1', path: 'r1',
          depth: 0, level: 1, name: 'Acme', kind: 'tenant', status: 'active',
          created_at: '2026-07-19T00:00:00Z',
        },
      ],
    });

    const subtree = httpMock.expectOne(`${base}/orgs/r1/subtree`);
    expect(subtree.request.method).toBe('GET');
    subtree.flush({
      organizations: [
        {
          org_id: 'r1', parent_org_id: null, root_org_id: 'r1', path: 'r1',
          depth: 0, level: 1, name: 'Acme', kind: 'tenant', status: 'active',
          created_at: '2026-07-19T00:00:00Z',
        },
        {
          org_id: 'c1', parent_org_id: 'r1', root_org_id: 'r1', path: 'r1.c1',
          depth: 1, level: 2, name: 'Platform', kind: 'division', status: 'active',
          created_at: '2026-07-19T00:00:00Z',
        },
      ],
    });

    fixture.detectChanges();
    const nodes = (fixture.nativeElement as HTMLElement).querySelectorAll('.tree__node');
    expect(nodes.length).toBe(2);
    expect(nodes[0].textContent).toContain('Acme');
    expect(nodes[1].textContent).toContain('Platform');
  });

  it('resolves visible projects for a subject', () => {
    const fixture = TestBed.createComponent(Organizations);
    fixture.detectChanges();
    httpMock.expectOne(`${base}/orgs`).flush({ organizations: [] });
    fixture.detectChanges();

    const component = fixture.componentInstance as unknown as {
      accessSubject: string;
      resolveAccess: () => void;
    };
    component.accessSubject = 'bob';
    component.resolveAccess();

    const req = httpMock.expectOne(`${base}/users/bob/visible-projects`);
    expect(req.request.method).toBe('GET');
    req.flush({
      subject: 'bob',
      projects: [
        { external_key: 'SAKAI', name: 'Sakai', repo_id: 'repo1', org_id: 'c1', provider: 'jira' },
      ],
    });

    fixture.detectChanges();
    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('.access-result tbody tr');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('SAKAI');
  });
});
