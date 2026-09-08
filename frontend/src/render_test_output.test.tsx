import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach } from 'vitest';
import OutputTab from './components/tabs/OutputTab';
import { usePipelineStore } from './state/pipelineStore';
import fs from 'fs';

describe('Render tests for OutputTab', () => {
  it('renders OutputTab correctly', () => {
    const run_id = "a129a4d099ac"; // the latest run
    const dir = `/Users/tanishkotian/slick_trace/backend/data/runs/${run_id}`;
    
    const pipelineStatus = JSON.parse(fs.readFileSync(`${dir}/pipeline_status.json`, 'utf8'));
    const shortlist = JSON.parse(fs.readFileSync(`${dir}/shortlist.json`, 'utf8').replace(/NaN/g, 'null'));
    const results = JSON.parse(fs.readFileSync(`${dir}/ranked_suspects.json`, 'utf8'));

    // Inject state
    usePipelineStore.setState({
      pipelineStatus,
      shortlist,
      results,
      runId: run_id
    });

    const { container: outContainer } = render(<OutputTab />);
    console.log("=== OutputTab HTML ===");
    console.log(outContainer.innerHTML);
  });
});
