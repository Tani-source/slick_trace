import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach } from 'vitest';
import fs from 'fs';
import path from 'path';
import InputTab from './tabs/InputTab';
import SuspectsTab from './tabs/SuspectsTab';
import OutputTab from './tabs/OutputTab';
import BottomPanel from './layout/BottomPanel';
import { usePipelineStore } from '../state/pipelineStore';

// NO mocks — tests real store and live backend fetch requests over http://localhost:8000

describe('LIVE UNMOCKED FRONTEND E2E WORKFLOW', () => {
  beforeEach(() => {
    usePipelineStore.getState().reset();
  });

  it('Drives full pipeline end-to-end through React components and live backend', async () => {
    // ── Step 1: Render InputTab ─────────────────────────────────────────────
    const { container, rerender } = render(<InputTab />);

    // Read real demo_scene.tif file bytes
    const sarFilePath = '/Users/tanishkotian/slick_trace/backend/data/synthetic/sar/demo_scene.tif';
    const sarBuffer = fs.readFileSync(sarFilePath);
    const sarArrayBuffer = sarBuffer.buffer.slice(sarBuffer.byteOffset, sarBuffer.byteOffset + sarBuffer.byteLength);
    const realSarFile = new File([sarArrayBuffer], 'demo_scene.tif', { type: 'image/tiff' });

    // Select SAR file on the actual file input in InputTab
    const sarInput = container.querySelector('input[accept=".tif,.tiff"]') as HTMLInputElement;
    expect(sarInput).not.toBeNull();

    fireEvent.change(sarInput, { target: { files: [realSarFile] } });

    // Wait for live backend upload response & Zustand store update
    let activeRunId = '';
    await waitFor(
      () => {
        activeRunId = usePipelineStore.getState().runId || '';
        expect(activeRunId).not.toBe('');
        expect(usePipelineStore.getState().datasets.sar.status).toBe('uploaded');
      },
      { timeout: 10000 }
    );

    console.log('>>> [LIVE E2E TEST] Generated Run ID from File Upload:', activeRunId);

    // Re-render InputTab to reflect updated store state
    rerender(<InputTab />);

    // Assert UI updated to "Ready", real filename, and ACTIVE RUN text
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('demo_scene.tif')).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`ACTIVE RUN: ${activeRunId}`, 'i'))).toBeInTheDocument();

    // ── Step 2: Click "Run Analysis Pipeline (Stages 0–4)" in InputTab ──────
    const runAnalysisBtn = screen.getByText('Run Analysis Pipeline (Stages 0–4)');
    expect(runAnalysisBtn).not.toBeDisabled();

    fireEvent.click(runAnalysisBtn);

    // Wait for Stage 0-4 execution & shortlist generation
    await waitFor(
      () => {
        const shortlist = usePipelineStore.getState().shortlist;
        expect(shortlist).not.toBeNull();
        expect(shortlist?.candidates.length).toBeGreaterThan(0);
      },
      { timeout: 15000 }
    );

    const shortlistData = usePipelineStore.getState().shortlist!;
    console.log('>>> [LIVE E2E TEST] Stage 0-4 Shortlist Candidates count:', shortlistData.candidates.length);
    console.log('>>> [LIVE E2E TEST] Top Candidate Anomaly Score:', shortlistData.candidates[0].anomaly_score);

    // ── Step 3: Render SuspectsTab & BottomPanel ────────────────────────────
    rerender(
      <>
        <SuspectsTab />
        <BottomPanel />
      </>
    );

    // Confirm candidate vessel name and decoupled Anomaly Score display on screen
    expect(screen.getByText(/SYNTH_TANKER_1/i)).toBeInTheDocument();
    expect(screen.getByText('ANOMALY SCORE')).toBeInTheDocument();

    // Confirm BottomPanel button text dynamically flipped from (0-4) to "Simulate Drift (5–6)"
    const simulateBtn = screen.getByText('Simulate Drift (5–6)');
    expect(simulateBtn).toBeInTheDocument();

    // ── Step 4: Click "Simulate Drift (5–6)" in BottomPanel ────────────────
    fireEvent.click(simulateBtn);

    // Wait for Stage 5-6 simulation & ranking completion
    await waitFor(
      () => {
        const results = usePipelineStore.getState().results;
        expect(results).not.toBeNull();
        expect(results?.ranking.length).toBeGreaterThan(0);
      },
      { timeout: 15000 }
    );

    const resultsData = usePipelineStore.getState().results!;
    console.log('>>> [LIVE E2E TEST] Stage 6 Rank 1 Match Score:', resultsData.ranking[0].match_score);

    // ── Step 5: Render OutputTab & BottomPanel ──────────────────────────────
    rerender(
      <>
        <OutputTab />
        <BottomPanel />
      </>
    );

    // Confirm decoupled score headers in OutputTab table
    expect(screen.getByText('MATCH SCORE')).toBeInTheDocument();
    expect(screen.getByText('ANOMALY SCORE')).toBeInTheDocument();

    // Confirm fallback badge rendering in BottomPanel
    const fallbackBadge = screen.getByText('(⚠ Synthetic Polygon)');
    expect(fallbackBadge).toBeInTheDocument();

    console.log('>>> [LIVE E2E TEST] FULL FRONTEND-TO-BACKEND PIPELINE WALKTHROUGH PASSED SUCCESSFULLY!');
  }, 60000);
});
