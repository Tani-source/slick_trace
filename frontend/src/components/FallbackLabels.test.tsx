import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { usePipelineStore } from '../state/pipelineStore';
import BottomPanel from './layout/BottomPanel';

vi.mock('../state/pipelineStore', () => ({
  usePipelineStore: vi.fn(),
}));

describe('Fallback Labels Verification in BottomPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "(⚠ Synthetic Polygon)" in BottomPanel when fallback_used is true', () => {
    (usePipelineStore as any).mockReturnValue({
      pipelineStatus: { stages: [] },
      slick: { area_km2: 12.5, age_estimate_hours: 12.0, fallback_used: true },
      shortlist: null,
      results: null,
      runningPipeline: false,
      runId: 'test_run',
      startPipeline: vi.fn(),
      startSimulation: vi.fn(),
    });

    render(<BottomPanel />);
    expect(screen.getByText('(⚠ Synthetic Polygon)')).toBeInTheDocument();
  });
});
