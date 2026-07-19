import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { ProjectsList } from './projects-list';

describe('ProjectsList', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProjectsList],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates and loads projects into the table on init', fakeAsync(() => {
    const fixture = TestBed.createComponent(ProjectsList);
    fixture.detectChanges();

    // The search stream debounces for 300ms before issuing the request.
    tick(300);

    const req = httpMock.expectOne((r) => r.url === `${environment.apiBaseUrl}/api/v1/projects`);
    req.flush({
      items: [
        { project_key: 'APACHE', name: 'Apache', category: 'infra', issue_count: 10, open_issue_count: 3 },
      ],
      page: { total: 1, limit: 50, offset: 0 },
    });

    fixture.detectChanges();
    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('tbody tr');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('APACHE');
  }));
});
