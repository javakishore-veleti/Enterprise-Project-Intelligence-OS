import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { AdminService } from './admin.service';
import { AgentConfig, AgentConfigListResponse, UpsertAgentConfigRequest } from '../models/admin';

describe('AdminService', () => {
  let service: AdminService;
  let httpMock: HttpTestingController;
  const base = `${environment.apiBaseUrl}/api/v1/admin`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AdminService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AdminService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lists agents with limit and offset params', () => {
    const stub: AgentConfigListResponse = {
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
      page: { total: 1, limit: 50, offset: 0 },
    };

    let result: AgentConfigListResponse | undefined;
    service.listAgents({ limit: 50, offset: 0 }).subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${base}/agents?limit=50&offset=0`);
    expect(req.request.method).toBe('GET');
    req.flush(stub);

    expect(result).toEqual(stub);
  });

  it('upserts an agent via PUT with the request body', () => {
    const body: UpsertAgentConfigRequest = {
      enabled: false,
      model: 'claude-sonnet-5',
      framework: 'openai_agents',
      prompt_ref: null,
      updated_by: 'admin',
    };
    const response: AgentConfig = {
      agent_key: 'schedule_risk',
      display_name: 'Schedule Risk',
      enabled: false,
      model: 'claude-sonnet-5',
      framework: 'openai_agents',
      prompt_ref: null,
      updated_by: 'admin',
      updated_at: '2026-07-19T01:00:00Z',
    };

    let result: AgentConfig | undefined;
    service.upsertAgent('schedule_risk', body).subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${base}/agents/schedule_risk`);
    expect(req.request.method).toBe('PUT');
    expect(req.request.body).toEqual(body);
    req.flush(response);

    expect(result).toEqual(response);
  });

  it('fetches audit history and system health', () => {
    service.getAudit({ limit: 50 }).subscribe();
    const auditReq = httpMock.expectOne(`${base}/audit?limit=50`);
    expect(auditReq.request.method).toBe('GET');
    auditReq.flush({ items: [], page: { total: 0, limit: 50, offset: 0 } });

    service.getSystemHealth().subscribe();
    const healthReq = httpMock.expectOne(`${base}/system/health`);
    expect(healthReq.request.method).toBe('GET');
    healthReq.flush({
      status: 'ok',
      service: 'admin-api',
      dependencies: { postgres: 'ok' },
      agent_count: 16,
      enabled_agent_count: 2,
    });
  });
});
