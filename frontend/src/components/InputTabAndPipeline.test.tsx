import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import InputTab from './tabs/InputTab';
import BottomPanel from './layout/BottomPanel';
import { usePipelineStore } from '../state/pipelineStore';

vi.mock('../state/pipelineStore', () => ({
  usePipelineStore: vi.fn(),
}));

describe('Frontend InputTab & BottomPanel Integration Verification', () => {
  let mockUpload: ReturnType<typeof vi.fn>;
  let mockStartPipeline: ReturnType<typeof vi.fn>;
  let mockStartSimulation: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockUpload = vi.fn().mockResolvedValue(undefined);
    mockStartPipeline = vi.fn().mockResolvedValue(undefined);
    mockStartSimulation = vi.fn().mockResolvedValue(undefined);
  });

  it('1. File Selection in InputTab triggers store upload action with file', async () => {
    (usePipelineStore as any).mockReturnValue({
      runId: 'run_123',
      datasets: {
        sar: { status: 'not_uploaded' },
        ais: { status: 'not_uploaded' },
        wind: { status: 'not_uploaded' },
        current: { status: 'not_uploaded' },
      },
      pipelineStatus: null,
      runningPipeline: false,
      upload: mockUpload,
      startPipeline: mockStartPipeline,
      startSimulation: mockStartSimulation,
    });

    const { container } = render(<InputTab />);

    // Query hidden file input for SAR imagery
    const sarInput = container.querySelector('input[accept=".tif,.tiff"]') as HTMLInputElement;
    expect(sarInput).not.toBeNull();

    const dummyFile = new File(['fake tiff data'], 'test_sar.tif', { type: 'image/tiff' });
    fireEvent.change(sarInput, { target: { files: [dummyFile] } });

    await waitFor(() => {
      expect(mockUpload).toHaveBeenCalledWith('sar', dummyFile, 'user_upload');
    });
  });

  it('2. Uploaded dataset state renders "Ready", real filename, and provenance badge', () => {
    (usePipelineStore as any).mockReturnValue({
      runId: 'run_123',
      datasets: {
        sar: {
          status: 'uploaded',
          file_name: 'test_sar.tif',
          provenance: 'illustrative',
          size_bytes: 204800,
          bbox: [28.4, -94.6, 29.4, -93.6],
        },
        ais: { status: 'not_uploaded' },
        wind: { status: 'not_uploaded' },
        current: { status: 'not_uploaded' },
      },
      pipelineStatus: null,
      runningPipeline: false,
      upload: mockUpload,
      startPipeline: mockStartPipeline,
      startSimulation: mockStartSimulation,
    });

    render(<InputTab />);

    // Verify Ready status text
    expect(screen.getByText('Ready')).toBeInTheDocument();
    // Verify real filename display
    expect(screen.getByText('test_sar.tif')).toBeInTheDocument();
    // Verify provenance tag display
    expect(screen.getByText(/illustrative/i)).toBeInTheDocument();
    // Verify size display (204800 bytes = 200.0 KB)
    expect(screen.getByText('200.0 KB')).toBeInTheDocument();
  });

  it('3. "Run Analysis Pipeline" button in InputTab invokes startPipeline()', () => {
    (usePipelineStore as any).mockReturnValue({
      runId: 'run_123',
      datasets: {
        sar: { status: 'uploaded', file_name: 'test_sar.tif' },
        ais: { status: 'not_uploaded' },
        wind: { status: 'not_uploaded' },
        current: { status: 'not_uploaded' },
      },
      pipelineStatus: null,
      runningPipeline: false,
      upload: mockUpload,
      startPipeline: mockStartPipeline,
      startSimulation: mockStartSimulation,
    });

    render(<InputTab />);

    const runBtn = screen.getByText('Run Analysis Pipeline (Stages 0–4)');
    expect(runBtn).not.toBeDisabled();

    fireEvent.click(runBtn);
    expect(mockStartPipeline).toHaveBeenCalledTimes(1);
  });

  it('4. BottomPanel button text and action flips based on shortlist state', () => {
    // Initial State: No shortlist -> Displays "Run Analysis Pipeline (0–4)" -> calls startPipeline()
    (usePipelineStore as any).mockReturnValue({
      runId: 'run_123',
      pipelineStatus: null,
      slick: null,
      shortlist: null,
      results: null,
      runningPipeline: false,
      startPipeline: mockStartPipeline,
      startSimulation: mockStartSimulation,
    });

    const { rerender } = render(<BottomPanel />);

    const primaryBtnInitial = screen.getByText('Run Analysis Pipeline (0–4)');
    expect(primaryBtnInitial).toBeInTheDocument();

    fireEvent.click(primaryBtnInitial);
    expect(mockStartPipeline).toHaveBeenCalledTimes(1);
    expect(mockStartSimulation).not.toHaveBeenCalled();

    // Updated State: Shortlist exists -> Button text flips to "Simulate Drift (5–6)" -> calls startSimulation()
    (usePipelineStore as any).mockReturnValue({
      runId: 'run_123',
      pipelineStatus: { stages: [] },
      slick: { area_km2: 12.4, age_estimate_hours: 12.0, fallback_used: false },
      shortlist: {
        candidates: [
          { mmsi: '111111111', vessel_name: 'TANKER 1', anomaly_score: 0.7, anomaly_breakdown: {} },
        ],
      },
      results: null,
      runningPipeline: false,
      startPipeline: mockStartPipeline,
      startSimulation: mockStartSimulation,
    });

    rerender(<BottomPanel />);

    const primaryBtnFlipped = screen.getByText('Simulate Drift (5–6)');
    expect(primaryBtnFlipped).toBeInTheDocument();

    fireEvent.click(primaryBtnFlipped);
    expect(mockStartSimulation).toHaveBeenCalledTimes(1);
  });
});
