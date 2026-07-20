import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { ProjectRisk } from './project-risk';
import { AnalysisRun, AnalysisRunsResponse } from '../models/analysis';
import { ProjectMetrics } from '../models/project';

const metricsStub: ProjectMetrics = {
  project_key: 'APACHE',
  computed_at: '2026-07-19T00:00:00Z',
  backlog_growth: 0.125,
  reopen_rate: 0.08,
  blocker_count: 4,
  dependency_depth: 3,
  issue_aging_days: 27,
  resolution_velocity: 1.5,
  contributor_concentration: 0.62,
  critical_defect_ratio: 0.15,
};

const runsStub: AnalysisRunsResponse = {
  project_key: 'APACHE',
  runs: [
    {
      run_id: 'run-9',
      project_key: 'APACHE',
      status: 'COMPLETED',
      agent_keys: ['schedule_risk', 'quality_risk'],
      started_at: '2026-07-19T00:00:00Z',
      finished_at: '2026-07-19T00:01:00Z',
      finding_count: 3,
      report_count: 1,
    },
  ],
};

describe('ProjectRisk', () => {
  let httpMock: HttpTestingController;

  const metricsUrl = `${environment.apiBaseUrl}/api/v1/projects/APACHE/metrics`;
  const analysisUrl = `${environment.riskApiBaseUrl}/api/v1/analysis/projects/APACHE`;
  const runsUrl = `${environment.riskApiBaseUrl}/api/v1/analysis/projects/APACHE/runs?limit=20`;

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

  it('loads and renders the computed-metrics panel and history table', () => {
    const fixture = TestBed.createComponent(ProjectRisk);
    fixture.detectChanges();

    (fixture.nativeElement as HTMLElement)
      .querySelector('.risk__btn--ghost')!
      .dispatchEvent(new Event('click'));

    httpMock.expectOne(metricsUrl).flush(metricsStub);
    httpMock.expectOne(runsUrl).flush(runsStub);
    fixture.detectChanges();

    const tiles = (fixture.nativeElement as HTMLElement).querySelectorAll('.tile');
    expect(tiles.length).toBe(8);
    // Ratios rendered as percentages, aging as "Nd".
    const panelText = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(panelText).toContain('12.5%'); // backlog_growth
    expect(panelText).toContain('27d'); // issue_aging_days
    expect(panelText).toContain('1.50'); // resolution_velocity

    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('tbody tr');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('COMPLETED');
    expect(rows[0].textContent).toContain('schedule_risk');
  });

  it('shows the "no metrics yet" note on a 404', () => {
    const fixture = TestBed.createComponent(ProjectRisk);
    fixture.detectChanges();

    (fixture.nativeElement as HTMLElement)
      .querySelector('.risk__btn--ghost')!
      .dispatchEvent(new Event('click'));

    httpMock.expectOne(metricsUrl).flush(
      { detail: 'not found' },
      { status: 404, statusText: 'Not Found' },
    );
    httpMock.expectOne(runsUrl).flush({ project_key: 'APACHE', runs: [] });
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No metrics yet');
  });

  it('runs an analysis and renders findings + per-agent breakdown, then refreshes history', () => {
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

    // The submit button triggers ngSubmit on the form.
    (fixture.nativeElement as HTMLElement)
      .querySelector('form')!
      .dispatchEvent(new Event('submit'));

    // runAnalysis refreshes metrics alongside the POST.
    httpMock.expectOne(metricsUrl).flush(metricsStub);

    const req = httpMock.expectOne(analysisUrl);
    expect(req.request.method).toBe('POST');
    expect(req.request.body.agents).toEqual(['schedule_risk', 'quality_risk']);
    req.flush(run);

    // Success path reloads the history table.
    httpMock.expectOne(runsUrl).flush(runsStub);
    fixture.detectChanges();

    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('.risk__table');
    // First table is history, second is findings.
    expect(rows.length).toBe(2);

    const findingRows = rows[1].querySelectorAll('tbody tr');
    expect(findingRows.length).toBe(2);
    // Sorted by score desc → the CRITICAL finding is first.
    expect(findingRows[0].textContent).toContain('CRITICAL');
    expect(findingRows[0].textContent).toContain('rank 1');

    // Per-agent breakdown: one tile per agent_key.
    const breakdown = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(breakdown).toContain('Agent execution');

    const reports = (fixture.nativeElement as HTMLElement).querySelectorAll('.report');
    expect(reports.length).toBe(1);
    expect(reports[0].textContent).toContain('Executive summary');
  });

  it('shows a friendly error when the analysis API is unreachable', () => {
    const fixture = TestBed.createComponent(ProjectRisk);
    fixture.detectChanges();

    (fixture.nativeElement as HTMLElement)
      .querySelector('form')!
      .dispatchEvent(new Event('submit'));

    // Metrics refresh fires alongside the analysis POST.
    httpMock.expectOne(metricsUrl).flush(metricsStub);
    httpMock.expectOne(analysisUrl).error(new ProgressEvent('error'));

    fixture.detectChanges();
    const err = (fixture.nativeElement as HTMLElement).querySelector('.risk__status--error');
    expect(err?.textContent).toContain('RiskAnalytics-API');
  });
});
