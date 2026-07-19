import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { AdminService } from './admin.service';
import {
  AgentConfig,
  AgentConfigListResponse,
  DatasetStatus,
  IngestionProgress,
  UpsertAgentConfigRequest,
} from '../models/admin';

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

  it('fetches dataset status via GET', () => {
    const stub: DatasetStatus = {
      dataset_id: 'msr-issue-tracking',
      title: 'MSR Issue-Tracking Dataset',
      state: 'NOT_DOWNLOADED',
      file_name: 'dataset.tar.gz',
      size_bytes: 6227702088,
      expected_md5: 'abc123',
      downloaded_bytes: 0,
      message: 'Not started.',
      updated_at: '2026-07-19T00:00:00Z',
    };

    let result: DatasetStatus | undefined;
    service.getDatasetStatus().subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${base}/dataset/status`);
    expect(req.request.method).toBe('GET');
    req.flush(stub);

    expect(result).toEqual(stub);
  });

  it('triggers a dataset download via POST with requested_by body', () => {
    const response: DatasetStatus = {
      dataset_id: 'msr-issue-tracking',
      title: 'MSR Issue-Tracking Dataset',
      state: 'DOWNLOADING',
      file_name: 'dataset.tar.gz',
      size_bytes: 6227702088,
      expected_md5: 'abc123',
      downloaded_bytes: 1024,
      message: 'Download started.',
      updated_at: '2026-07-19T01:00:00Z',
    };

    let result: DatasetStatus | undefined;
    service.triggerDatasetDownload('admin').subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${base}/dataset/download`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ requested_by: 'admin' });
    req.flush(response);

    expect(result).toEqual(response);
  });

  it('fetches the latest ingestion progress via GET', () => {
    const stub: IngestionProgress = {
      run_id: null,
      dataset_id: 'msr-issue-tracking',
      status: 'NOT_STARTED',
      started_at: null,
      finished_at: null,
      records_done: 0,
      records_total: 0,
      entities: [],
      recent_log: [],
    };

    let result: IngestionProgress | undefined;
    service.getIngestionStatus().subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${base}/dataset/ingestion`);
    expect(req.request.method).toBe('GET');
    req.flush(stub);

    expect(result).toEqual(stub);
  });

  it('triggers a dataset ingestion via POST with requested_by body', () => {
    const response: IngestionProgress = {
      run_id: 'run-1',
      dataset_id: 'msr-issue-tracking',
      status: 'RUNNING',
      started_at: '2026-07-19T01:00:00Z',
      finished_at: null,
      records_done: 100,
      records_total: 2700000,
      entities: [{ entity: 'issues', records_done: 100, records_total: 2700000, status: 'RUNNING' }],
      recent_log: [
        {
          level: 'INFO',
          entity: 'issues',
          message: 'Ingestion started.',
          records_done: 100,
          records_total: 2700000,
          created_at: '2026-07-19T01:00:00Z',
        },
      ],
    };

    let result: IngestionProgress | undefined;
    service.triggerDatasetIngest('admin').subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${base}/dataset/ingest`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ requested_by: 'admin' });
    req.flush(response);

    expect(result).toEqual(response);
  });
});
