import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { AuditList } from './audit-list';

const base = `${environment.apiBaseUrl}/api/v1/admin`;

describe('AuditList', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AuditList],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('loads audit events into the table on init', () => {
    const fixture = TestBed.createComponent(AuditList);
    fixture.detectChanges();

    const req = httpMock.expectOne((r) => r.url === `${base}/audit`);
    expect(req.request.method).toBe('GET');
    req.flush({
      items: [
        {
          event_id: 'e1',
          entity_type: 'agent_config',
          entity_key: 'schedule_risk',
          action: 'update',
          actor: 'admin',
          details: { framework: 'openai_agents' },
          created_at: '2026-07-19T00:00:00Z',
        },
      ],
      page: { total: 1, limit: 100, offset: 0 },
    });

    fixture.detectChanges();
    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('tbody tr');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('update');
    expect(rows[0].textContent).toContain('schedule_risk');
  });
});
