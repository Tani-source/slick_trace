import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { usePipelineStore } from '../state/pipelineStore';
import TabResults from './sidebar/TabResults';
import TabShortlist from './sidebar/TabShortlist';
import StatsStrip from './bottompanel/StatsStrip';

// Mock zustand store
vi.mock('../state/pipelineStore', () => ({
  usePipelineStore: vi.fn(),
}));

// Mock ui store
vi.mock('../state/uiStore', () => ({
  useUiStore: () => ({
    darkShipEnabled: false,
    setDarkShipEnabled: vi.fn(),
    oilTypeEnabled: false,
    setOilTypeEnabled: vi.fn(),
    setHighlightedMmsi: vi.fn(),
  }),
}));

describe('Fallback Labels Verification', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "⚠ Numpy Fallback" for MatchScore in TabResults', () => {
    // Setup store mock with fallback_used: true in simulatedFootprints
    (usePipelineStore as any).mockReturnValue({
      runId: 'test_run',
      pipelineStatus: { stages: [{ name: 'verification_matching', status: 'done' }] },
      shortlist: {
        candidates: [
          {
            mmsi: '123456789',
            vessel_name: 'TEST VESSEL',
            anomaly_score: 0.9,
            anomaly_breakdown: { blackout: 1, speed: 0.5, route: 0.1, draft: 0.05 },
            position_at_event: { lat: 0, lon: 0, time: '' },
          },
        ],
      },
      results: {
        ranking: [
          { mmsi: '123456789', vessel_name: 'TEST VESSEL', match_score: 0.85, iou: 0.8, centroid_distance_km: 5, rank: 1 },
        ],
      },
      simulatedFootprints: {
        simulations: [{ mmsi: '123456789', fallback_used: true }],
      },
    });

    render(<TabResults />);
    expect(screen.getByText('⚠ Numpy Fallback')).toBeInTheDocument();
  });

  it('renders "(Mocked)" for Route and Draft in TabShortlist', () => {
    (usePipelineStore as any).mockReturnValue({
      shortlist: {
        candidates: [
          {
            mmsi: '123456789',
            vessel_name: 'TEST VESSEL',
            anomaly_score: 0.9,
            anomaly_breakdown: { blackout: 1, speed: 0.5, route: 0.1, draft: 0.05 },
            position_at_event: { lat: 0, lon: 0, time: '' },
          },
        ],
      },
    });

    render(<TabShortlist />);
    // There should be two "(Mocked)" labels: one for Route and one for Draft
    const mockedLabels = screen.getAllByText('(Mocked)');
    expect(mockedLabels.length).toBe(2);
  });

  it('renders "(⚠ Synthetic Polygon)" and "(⚠ Numpy Fallback)" in StatsStrip', () => {
    (usePipelineStore as any).mockReturnValue({
      pipelineStatus: { stages: [] },
      slickPolygon: { area_km2: 12.5, fallback_used: true },
      originEnvelope: { time_window_hours: 24, fallback_used: true },
      shortlist: null,
      runId: 'test',
    });

    render(<StatsStrip />);
    expect(screen.getByText('(⚠ Synthetic Polygon)')).toBeInTheDocument();
    expect(screen.getByText('(⚠ Numpy Fallback)')).toBeInTheDocument();
  });
});
