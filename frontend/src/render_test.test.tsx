import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach } from 'vitest';
import SuspectsTab from './components/tabs/SuspectsTab';
import OutputTab from './components/tabs/OutputTab';
import BottomPanel from './components/layout/BottomPanel';
import { usePipelineStore } from './state/pipelineStore';
import fs from 'fs';

describe('Render tests for <0.01', () => {
  it('renders <0.01 correctly', () => {
    const run_id = "a129a4d099ac"; // the latest run
    const dir = `/Users/tanishkotian/slick_trace/backend/data/runs/${run_id}`;
    
    const pipelineStatus = JSON.parse(fs.readFileSync(`${dir}/pipeline_status.json`, 'utf8'));
    const shortlist = JSON.parse(fs.readFileSync(`${dir}/shortlist.json`, 'utf8').replace(/NaN/g, 'null'));
    const results = JSON.parse(fs.readFileSync(`${dir}/ranked_suspects.json`, 'utf8'));
    const slick = JSON.parse(fs.readFileSync(`${dir}/slick_polygon.json`, 'utf8').replace(/NaN/g, 'null'));

    // Inject state
    usePipelineStore.setState({
      pipelineStatus,
      shortlist,
      results,
      slick,
      runId: run_id
    });

    const { container: suspContainer } = render(<SuspectsTab />);
    console.log("=== SuspectsTab Rendered HTML (excerpt) ===");
    console.log(suspContainer.innerHTML.match(/MATCH SCORE.*?<div class="st-v">.*?<span[^>]*>(.*?)<\/span>/s)?.[1]);

    const { container: outContainer } = render(<OutputTab />);
    console.log("\n=== OutputTab Rendered HTML (excerpt) ===");
    // Find the td with var(--chart-teal-bright)
    const tealTds = outContainer.querySelectorAll('td[style*="--chart-teal-bright"]');
    console.log(Array.from(tealTds).map(td => td.innerHTML).join(', '));

    const { container: botContainer } = render(<BottomPanel />);
    console.log("\n=== BottomPanel Rendered HTML (excerpt) ===");
    const matchSpan = botContainer.innerHTML.match(/MATCH: (.*?)<\/b>/s)?.[1];
    console.log("Top Score text: MATCH:", matchSpan);
  });
});
