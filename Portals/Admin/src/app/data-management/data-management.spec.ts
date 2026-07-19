import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { DataManagement } from './data-management';

describe('DataManagement', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DataManagement],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('renders the sidebar with an Initial Dataset link', () => {
    const fixture = TestBed.createComponent(DataManagement);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const link = el.querySelector('.data-sidebar__link') as HTMLAnchorElement;
    expect(link).toBeTruthy();
    expect(link.textContent).toContain('Initial Dataset');
    expect(link.getAttribute('href')).toContain('/data/initial-dataset');
  });
});
