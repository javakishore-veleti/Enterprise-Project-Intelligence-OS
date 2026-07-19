import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { DatasetStatus, IngestionProgress } from '../models/admin';
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

function ingestion(overrides: Partial<IngestionProgress> = {}): IngestionProgress {
  return {
    run_id: null,
    dataset_id: 'msr-issue-tracking',
    status: 'NOT_STARTED',
    started_at: null,
    finished_at: null,
    records_done: 0,
    records_total: 0,
    entities: [],
    recent_log: [],
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
    httpMock.expectOne(`${base}/dataset/ingestion`).flush(ingestion());
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
    httpMock.expectOne(`${base}/dataset/ingestion`).flush(ingestion());
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
    httpMock
      .expectOne(`${base}/dataset/ingestion`)
      .error(new ProgressEvent('error'), { status: 0, statusText: 'Unknown Error' });
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.panel__status--error')?.textContent).toContain('Admin-API');
  });

  it('disables the ingest button until the dataset is DOWNLOADED', () => {
    const fixture = TestBed.createComponent(InitialDataset);
    fixture.detectChanges();
    httpMock.expectOne(`${base}/dataset/status`).flush(status({ state: 'NOT_DOWNLOADED' }));
    httpMock.expectOne(`${base}/dataset/ingestion`).flush(ingestion());
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const ingestBtn = el.querySelectorAll('.btn--primary')[1] as HTMLButtonElement;
    expect(ingestBtn.disabled).toBeTrue();
    expect(ingestBtn.textContent).toContain('Download the dataset first');
  });

  it('enables the ingest button when DOWNLOADED and NOT_STARTED', () => {
    const fixture = TestBed.createComponent(InitialDataset);
    fixture.detectChanges();
    httpMock.expectOne(`${base}/dataset/status`).flush(status({ state: 'DOWNLOADED' }));
    httpMock.expectOne(`${base}/dataset/ingestion`).flush(ingestion({ status: 'NOT_STARTED' }));
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const ingestBtn = el.querySelectorAll('.btn--primary')[1] as HTMLButtonElement;
    expect(ingestBtn.disabled).toBeFalse();
    expect(ingestBtn.textContent).toContain('Ingest into evidence store');
  });

  it('disables the ingest button and renders live progress while RUNNING', () => {
    const fixture = TestBed.createComponent(InitialDataset);
    fixture.detectChanges();
    httpMock.expectOne(`${base}/dataset/status`).flush(status({ state: 'DOWNLOADED' }));
    httpMock.expectOne(`${base}/dataset/ingestion`).flush(
      ingestion({
        run_id: 'run-1',
        status: 'RUNNING',
        started_at: '2026-07-19T01:00:00Z',
        records_done: 1350000,
        records_total: 2700000,
        entities: [
          { entity: 'issues', records_done: 1350000, records_total: 2700000, status: 'RUNNING' },
        ],
        recent_log: [
          {
            level: 'INFO',
            entity: 'issues',
            message: 'Ingesting issues batch.',
            records_done: 1350000,
            records_total: 2700000,
            created_at: '2026-07-19T01:00:00Z',
          },
        ],
      }),
    );
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const ingestBtn = el.querySelectorAll('.btn--primary')[1] as HTMLButtonElement;
    expect(ingestBtn.disabled).toBeTrue();
    expect(ingestBtn.textContent).toContain('Ingestion in progress');

    // Overall status badge + progress + per-entity table + activity log all render.
    expect(el.querySelector('.badge--ing-running')?.textContent).toContain('RUNNING');
    expect(el.textContent).toContain('50%');
    expect(el.querySelector('.ing-table')).not.toBeNull();
    expect(el.querySelector('.ing-table')?.textContent).toContain('issues');
    expect(el.querySelector('.ing-log')?.textContent).toContain('Ingesting issues batch.');

    // A poll is scheduled while RUNNING; destroy stops it before verify().
    fixture.destroy();
  });

  it('POSTs the ingest trigger when clicked and shows the returned status', () => {
    const fixture = TestBed.createComponent(InitialDataset);
    fixture.detectChanges();
    httpMock.expectOne(`${base}/dataset/status`).flush(status({ state: 'DOWNLOADED' }));
    httpMock.expectOne(`${base}/dataset/ingestion`).flush(ingestion({ status: 'NOT_STARTED' }));
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    (el.querySelectorAll('.btn--primary')[1] as HTMLButtonElement).click();

    const post = httpMock.expectOne(`${base}/dataset/ingest`);
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ requested_by: 'admin' });
    post.flush(ingestion({ run_id: 'run-1', status: 'PENDING', records_total: 2700000 }));
    fixture.detectChanges();

    expect(el.querySelector('.badge--ing-pending')?.textContent).toContain('PENDING');
    fixture.destroy();
  });

  it('shows a friendly 409 message when the dataset is not downloaded', () => {
    const fixture = TestBed.createComponent(InitialDataset);
    fixture.detectChanges();
    httpMock.expectOne(`${base}/dataset/status`).flush(status({ state: 'DOWNLOADED' }));
    httpMock.expectOne(`${base}/dataset/ingestion`).flush(ingestion({ status: 'FAILED' }));
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    (el.querySelectorAll('.btn--primary')[1] as HTMLButtonElement).click();

    httpMock
      .expectOne(`${base}/dataset/ingest`)
      .flush('conflict', { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    expect(el.querySelector('.panel__status--error')?.textContent).toContain('Download the dataset');
  });
});
