import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { AgentsList } from './agents-list';

const base = `${environment.apiBaseUrl}/api/v1/admin`;

describe('AgentsList', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AgentsList],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates and loads agent rows on init', () => {
    const fixture = TestBed.createComponent(AgentsList);
    fixture.detectChanges();

    const req = httpMock.expectOne((r) => r.url === `${base}/agents`);
    expect(req.request.method).toBe('GET');
    req.flush({
      items: [
        {
          agent_key: 'schedule_risk',
          display_name: 'Schedule Risk',
          enabled: true,
          model: 'claude-opus-4-8',
          framework: 'langgraph',
          prompt_ref: null,
          updated_by: 'admin',
          updated_at: '2026-07-19T00:00:00Z',
        },
      ],
      page: { total: 1, limit: 200, offset: 0 },
    });

    fixture.detectChanges();
    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('tbody tr');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('schedule_risk');
  });

  it('sends a PUT when a dirty row is saved', () => {
    const fixture = TestBed.createComponent(AgentsList);
    fixture.detectChanges();

    httpMock.expectOne((r) => r.url === `${base}/agents`).flush({
      items: [
        {
          agent_key: 'schedule_risk',
          display_name: 'Schedule Risk',
          enabled: true,
          model: 'claude-opus-4-8',
          framework: 'langgraph',
          prompt_ref: null,
          updated_by: 'admin',
          updated_at: '2026-07-19T00:00:00Z',
        },
      ],
      page: { total: 1, limit: 200, offset: 0 },
    });
    fixture.detectChanges();

    const component = fixture.componentInstance as unknown as {
      rows: () => { model: string }[];
      save: (row: unknown) => void;
    };
    const row = component.rows()[0];
    row.model = 'claude-sonnet-5';
    component.save(row);

    const put = httpMock.expectOne(`${base}/agents/schedule_risk`);
    expect(put.request.method).toBe('PUT');
    expect(put.request.body.model).toBe('claude-sonnet-5');
    put.flush({
      agent_key: 'schedule_risk',
      display_name: 'Schedule Risk',
      enabled: true,
      model: 'claude-sonnet-5',
      framework: 'langgraph',
      prompt_ref: null,
      updated_by: 'admin',
      updated_at: '2026-07-19T01:00:00Z',
    });
  });
});
