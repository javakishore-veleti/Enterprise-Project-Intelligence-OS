import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { DatasetStatus } from '../models/admin';
import { InitialDataset } from './initial-dataset';

const base = `${environment.apiBaseUrl}/api/v1/admin`;

function status(overrides: Partial<DatasetStatus> = {}): DatasetStatus {
  return {
    dataset_id: 'msr-issue-tracking',
    title: 'MSR Issue-Tracking Dataset',
    state: 'NOT_DOWNLOADED',
    file_name: 'dataset.tar.gz',
    size_bytes: 6227702088,
    expected_md5: 'abc123',
    downloaded_bytes: 0,
    message: 'Not started.',
    updated_at: '2026-07-19T00:00:00Z',
    ...overrides,
  };
}

describe('InitialDataset', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InitialDataset],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('loads and renders the dataset status on init', () => {
    const fixture = TestBed.createComponent(InitialDataset);
    fixture.detectChanges();

    const req = httpMock.expectOne(`${base}/dataset/status`);
    expect(req.request.method).toBe('GET');
    req.flush(status());
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('MSR Issue-Tracking Dataset');
    expect(el.querySelector('.badge')?.textContent).toContain('NOT_DOWNLOADED');
    // 6227702088 bytes ~ 5.8 GB
    expect(el.textContent).toContain('5.8 GB');

    const btn = el.querySelector('.btn--primary') as HTMLButtonElement;
    expect(btn.disabled).toBeFalse();
  });

  it('POSTs the trigger and disables the button once DOWNLOADED', () => {
    const fixture = TestBed.createComponent(InitialDataset);
    fixture.detectChanges();
    httpMock.expectOne(`${base}/dataset/status`).flush(status());
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('.btn--primary') as HTMLButtonElement).click();

    const post = httpMock.expectOne(`${base}/dataset/download`);
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ requested_by: 'admin' });
    post.flush(status({ state: 'DOWNLOADED', downloaded_bytes: 6227702088, message: 'Complete.' }));
    fixture.detectChanges();

    const btn = el.querySelector('.btn--primary') as HTMLButtonElement;
    expect(btn.disabled).toBeTrue();
    expect(el.textContent).toContain('Dataset already downloaded');
  });

  it('shows a friendly error when the API is unreachable', () => {
    const fixture = TestBed.createComponent(InitialDataset);
    fixture.detectChanges();

    httpMock
      .expectOne(`${base}/dataset/status`)
      .error(new ProgressEvent('error'), { status: 0, statusText: 'Unknown Error' });
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.panel__status--error')?.textContent).toContain('Admin-API');
  });
});
