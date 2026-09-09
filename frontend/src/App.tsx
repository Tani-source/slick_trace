import { useEffect, useRef, useState } from 'react';
import Sidebar from './components/sidebar/Sidebar';
import TopBar from './components/layout/TopBar';
import BottomPanel from './components/layout/BottomPanel';
import OutputTab from './components/tabs/OutputTab';
import InputTab from './components/tabs/InputTab';
import PipelineTab from './components/tabs/PipelineTab';
import SuspectsTab from './components/tabs/SuspectsTab';
import { getHealth } from './api/client';
import { useUiStore } from './state/uiStore';
import { usePipelineStore } from './state/pipelineStore';

// We map pipeline 'ready' datasets to determine HAS_DATA
export default function App() {
  const activeTab = useUiStore((s) => s.activeTab);
  const { connectionLost, setConnectionLost, datasets, pipelineStatus, runPipeline } = usePipelineStore();
  
  // hasData unlocks the pipeline tab execution view
  // It is true if ANY dataset is uploaded, OR if the pipeline status has already been fetched.
  const hasData = Object.values(datasets).some(d => d.status === 'uploaded') || !!pipelineStatus;
  
  const simulated = !!(pipelineStatus && Array.isArray(pipelineStatus.stages) && pipelineStatus.stages.find(s => s.name === 'drift_simulation' && s.status === 'done'));
  const simulating = !!(pipelineStatus && Array.isArray(pipelineStatus.stages) && pipelineStatus.stages.find(s => s.name === 'drift_simulation' && s.status === 'running'));

  // Health check: surface a connection banner when the API is unreachable.
  useEffect(() => {
    let stopped = false;
    const check = async () => {
      try {
        await getHealth();
        if (!stopped) setConnectionLost(false);
      } catch {
        if (!stopped) setConnectionLost(true);
      }
    };
    void check();
    const id = window.setInterval(() => void check(), 4000);
    return () => {
      stopped = true;
      window.clearInterval(id);
    };
  }, [setConnectionLost]);

  return (
    <div className="st-root">
      <div className="st-app">
        <Sidebar />

        <div className="st-main">
          {connectionLost && (
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 1000, background: 'var(--rust-bright)', color: '#fff', textAlign: 'center', padding: '4px', fontSize: '11px', fontWeight: 500 }}>
              Connection lost, retrying…
            </div>
          )}

          <div className={`st-view ${simulated ? 'split' : ''}`}>
            <TopBar />

            <div className={`st-viewport ${activeTab === 'output' ? 'active' : ''}`}>
              <OutputTab />
            </div>
            <div className={`st-viewport ${activeTab === 'input' ? 'active' : ''}`}>
              <InputTab />
            </div>
            <div className={`st-viewport ${activeTab === 'pipeline' ? 'active' : ''}`}>
              {/* Note: In a real app we'd map simProgress based on SSE/websockets. For this demo we use 50% if running. */}
              <PipelineTab hasData={hasData} simulating={simulating} simProgress={50} simulated={simulated} />
            </div>
            <div className={`st-viewport ${activeTab === 'suspects' ? 'active' : ''}`}>
              <SuspectsTab />
            </div>
          </div>

          <BottomPanel />
        </div>
      </div>
    </div>
  );
}
