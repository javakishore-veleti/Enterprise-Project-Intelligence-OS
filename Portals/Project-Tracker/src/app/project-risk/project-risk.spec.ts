import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { ProjectRisk } from './project-risk';
import { AnalysisRun } from '../models/analysis';

describe('ProjectRisk', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProjectRisk],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates with APACHE as the default project key', async () => {
    const fixture = TestBed.createComponent(ProjectRisk);
    fixture.detectChanges();
    // ngModel writes the initial value into the DOM asynchronously.
    await fixture.whenStable();
    const input = (fixture.nativeElement as HTMLElement).querySelector(
      'input[name="projectKey"]',
    ) as HTMLInputElement;
    expect(input.value).toBe('APACHE');
  });

  it('runs an analysis and renders findings sorted by score desc + reports', () => {
    const run: AnalysisRun = {
      run_id: 'run-1',
      project_key: 'APACHE',
      status: 'COMPLETED',
      agent_keys: ['schedule_risk', 'quality_risk'],
      started_at: '2026-07-19T00:00:00Z',
      finished_at: '2026-07-19T00:01:00Z',
      findings: [
        {
          finding_id: 'f-low',
          agent_key: 'quality_risk',
          risk_category: 'quality',
          probability: 0.3,
          impact: 0.4,
          severity: 'MEDIUM',
          score: 0.42,
          confidence: 0.6,
          explanation: 'Lower score finding',
          assumptions: [],
          recommended_actions: [],
          affected: [],
          analysis_timestamp: '2026-07-19T00:00:30Z',
          meta: {},
        },
        {
          finding_id: 'f-high',
          agent_key: 'schedule_risk',
          risk_category: 'schedule',
          probability: 0.8,
          impact: 0.9,
          severity: 'CRITICAL',
          score: 0.91,
          confidence: 0.85,
          explanation: 'Higher score finding',
          assumptions: [],
          recommended_actions: [],
          affected: [],
          analysis_timestamp: '2026-07-19T00:00:30Z',
          meta: { priority_rank: 1, critic_verdict: 'accept' },
        },
      ],
      reports: [
        {
          report_id: 'r-1',
          kind: 'executive',
          title: 'Executive summary',
          summary: 'Overall risk is elevated.',
          sections: [{ heading: 'Outlook', body: 'Details here.' }],
          source_agent: 'executive_reporting',
          generated_at: '2026-07-19T00:01:00Z',
        },
      ],
    };

    const fixture = TestBed.createComponent(ProjectRisk);
    fixture.detectChanges();

    (fixture.nativeElement as HTMLElement)
      .querySelector('.risk__btn')!
      .dispatchEvent(new Event('click'));
    // The submit button triggers ngSubmit on the form.
    (fixture.nativeElement as HTMLElement)
      .querySelector('form')!
      .dispatchEvent(new Event('submit'));

    const req = httpMock.expectOne(
      `${environment.riskApiBaseUrl}/api/v1/analysis/projects/APACHE`,
    );
    expect(req.request.method).toBe('POST');
    expect(req.request.body.agents).toEqual(['schedule_risk', 'quality_risk']);
    req.flush(run);

    fixture.detectChanges();

    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('tbody tr');
    expect(rows.length).toBe(2);
    // Sorted by score desc → the CRITICAL finding is first.
    expect(rows[0].textContent).toContain('CRITICAL');
    expect(rows[0].textContent).toContain('rank 1');

    const reports = (fixture.nativeElement as HTMLElement).querySelectorAll('.report');
    expect(reports.length).toBe(1);
    expect(reports[0].textContent).toContain('Executive summary');
  });

  it('shows a friendly error when the API is unreachable', () => {
    const fixture = TestBed.createComponent(ProjectRisk);
    fixture.detectChanges();

    (fixture.nativeElement as HTMLElement)
      .querySelector('form')!
      .dispatchEvent(new Event('submit'));

    const req = httpMock.expectOne(
      `${environment.riskApiBaseUrl}/api/v1/analysis/projects/APACHE`,
    );
    req.error(new ProgressEvent('error'));

    fixture.detectChanges();
    const err = (fixture.nativeElement as HTMLElement).querySelector('.risk__status--error');
    expect(err?.textContent).toContain('RiskAnalytics-API');
  });
});
