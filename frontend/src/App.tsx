import { useEffect } from 'react';
import { usePipelineStore } from './state/pipelineStore';
import { useUIStore } from './state/uiStore';
import Sidebar from './components/sidebar/Sidebar';
import MapCanvas from './components/map/MapCanvas';
import StatsStrip from './components/bottompanel/StatsStrip';
import TimelineScrubber from './components/bottompanel/TimelineScrubber';
import FloatingToolStack from './components/righttools/FloatingToolStack';

function App() {
  const connectionLost = usePipelineStore((s) => s.connectionLost);
  const setConnectionLost = usePipelineStore((s) => s.setConnectionLost);
  const maximize = useUIStore((s) => s.maximize);

  // Health check: surface a connection banner when the API is unreachable.
  useEffect(() => {
    let stopped = false;
    const check = async () => {
      try {
        const res = await fetch('/api/health');
        if (res.ok) {
          if (!stopped) setConnectionLost(false);
        } else if (!stopped) {
          setConnectionLost(true);
        }
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

const STAGE_LABELS: Record<string, string> = {
  perception: 'SAR Perception',
  ais_ingestion: 'AIS Ingestion',
  candidate_filtering: 'Candidate Filter',
  anomaly_scoring: 'Anomaly Scoring',
  drift_simulation: 'Drift Simulation',
  verification_matching: 'Verification & Match',
};

function TabInput() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex flex-1 overflow-hidden">
        {!maximize && <Sidebar />}
        <div className="relative flex-1 min-w-0">
          <MapCanvas />
          {!maximize && <FloatingToolStack />}
          {connectionLost && (
            <div className="absolute top-0 left-0 right-0 z-[1001] bg-accent-amber text-ocean text-center py-1 text-caption font-medium">
              Connection lost, retrying…
            </div>
          )}
        </div>
      </div>
      {!maximize && (
        <div className="h-24 bg-panel border-t border-border-subtle flex items-center shrink-0">
          <StatsStrip />
          <div className="w-px h-12 bg-border-subtle" />
          <TimelineScrubber />
        </div>
      )}
    </div>
  );
}

export default App;
