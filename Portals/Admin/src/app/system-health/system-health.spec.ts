import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { SystemHealth } from './system-health';

const base = `${environment.apiBaseUrl}/api/v1/admin`;

describe('SystemHealth', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SystemHealth],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('renders health counts and dependencies on init', () => {
    const fixture = TestBed.createComponent(SystemHealth);
    fixture.detectChanges();

    const req = httpMock.expectOne(`${base}/system/health`);
    expect(req.request.method).toBe('GET');
    req.flush({
      status: 'ok',
      service: 'admin-api',
      dependencies: { postgres: 'ok' },
      agent_count: 16,
      enabled_agent_count: 2,
    });

    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('16');
    expect(text).toContain('postgres');
  });
});
