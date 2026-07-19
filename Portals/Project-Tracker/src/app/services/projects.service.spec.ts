import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { ProjectsService } from './projects.service';
import { ProjectSearchResponse } from '../models/project';

describe('ProjectsService', () => {
  let service: ProjectsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ProjectsService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ProjectsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('searches projects with query and limit params', () => {
    const stub: ProjectSearchResponse = {
      items: [
        { project_key: 'APACHE', name: 'Apache', category: 'infra', issue_count: 10, open_issue_count: 3 },
      ],
      page: { total: 1, limit: 50, offset: 0 },
    };

    let result: ProjectSearchResponse | undefined;
    service.searchProjects({ query: 'apa', limit: 50 }).subscribe((r) => (result = r));

    const req = httpMock.expectOne(
      `${environment.apiBaseUrl}/api/v1/projects?query=apa&limit=50`,
    );
    expect(req.request.method).toBe('GET');
    req.flush(stub);

    expect(result).toEqual(stub);
  });

  it('fetches a single project by key', () => {
    service.getProject('APACHE').subscribe();
    const req = httpMock.expectOne(`${environment.apiBaseUrl}/api/v1/projects/APACHE`);
    expect(req.request.method).toBe('GET');
    req.flush({ project_key: 'APACHE', name: 'Apache', category: null, issue_count: 0, open_issue_count: 0 });
  });
});
