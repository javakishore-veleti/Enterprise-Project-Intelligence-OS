import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { RiskAnalyticsService } from './risk-analytics.service';
import { AnalysisRun } from '../models/analysis';

describe('RiskAnalyticsService', () => {
  let service: RiskAnalyticsService;
  let httpMock: HttpTestingController;

  const runStub: AnalysisRun = {
    run_id: 'run-123',
    project_key: 'APACHE',
    status: 'COMPLETED',
    agent_keys: ['schedule_risk'],
    started_at: '2026-07-19T00:00:00Z',
    finished_at: '2026-07-19T00:01:00Z',
    findings: [],
    reports: [],
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [RiskAnalyticsService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(RiskAnalyticsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('POSTs the analysis request body for a project key', () => {
    let result: AnalysisRun | undefined;
    service
      .startAnalysis('APACHE', {
        agents: ['schedule_risk', 'quality_risk'],
        includeReview: true,
        requestedBy: 'tester',
      })
      .subscribe((r) => (result = r));

    const req = httpMock.expectOne(
      `${environment.riskApiBaseUrl}/api/v1/analysis/projects/APACHE`,
    );
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      agents: ['schedule_risk', 'quality_risk'],
      include_review: true,
      requested_by: 'tester',
    });
    req.flush(runStub);

    expect(result).toEqual(runStub);
  });

  it('GETs a run by id', () => {
    service.getRun('run-123').subscribe();
    const req = httpMock.expectOne(
      `${environment.riskApiBaseUrl}/api/v1/analysis/runs/run-123`,
    );
    expect(req.request.method).toBe('GET');
    req.flush(runStub);
  });
});
