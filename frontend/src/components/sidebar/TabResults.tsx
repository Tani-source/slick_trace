import { useState } from 'react';
import { usePipelineStore } from '../../state/pipelineStore';
import { useUIStore } from '../../state/uiStore';
import { simulatePipeline } from '../../api/client';
import { MapPin } from 'lucide-react';

function ConfidenceBadge({ value, label }: { value: number; label: string }) {
  const color =
    value >= 0.7 ? 'var(--color-accent-green)' : value >= 0.4 ? 'var(--color-accent-amber)' : 'var(--color-accent-red)';
  return (
    <span
      className="px-2 py-0.5 rounded-full text-caption font-medium"
      style={{ background: `${color}22`, color }}
    >
      {label} {value.toFixed(2)}
    </span>
  );
}

export default function TabResults() {
  const results = usePipelineStore((s) => s.results);
  const shortlist = usePipelineStore((s) => s.shortlist);
  const runId = usePipelineStore((s) => s.runId);
  const pipelineStatus = usePipelineStore((s) => s.pipelineStatus);
  const setSplitView = useUIStore((s) => s.setSplitView);
  const splitView = useUIStore((s) => s.splitView);
  const [simError, setSimError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const shortlistReady = !!shortlist && shortlist.candidates.length > 0;
  const runningStage = pipelineStatus?.stages.find((s) => s.status === 'running');
  const anomalyByMmsi = new Map(shortlist?.candidates.map((c) => [c.mmsi, c]) ?? []);

  const handleSimulate = async () => {
    if (!runId) return;
    setRunning(true);
    setSimError(null);
    try {
      await simulatePipeline(runId);
    } catch (e) {
      setSimError(e instanceof Error ? e.message : 'Simulation failed');
    } finally {
      setRunning(false);
    }
  };

  if (!results || results.ranking.length === 0) {
    return (
      <div className="flex flex-col gap-4 p-4 flex-1 overflow-y-auto">
        <button
          type="button"
          disabled={!shortlistReady || running}
          title={shortlistReady ? '' : 'Upload all 4 datasets and generate a shortlist first.'}
          className="w-full py-3 rounded-md text-display font-medium transition"
          style={
            shortlistReady && !running
              ? { background: 'var(--color-accent-teal)', color: '#0B1E3D' }
              : { background: 'var(--color-panel-raised)', color: 'var(--color-text-disabled)' }
          }
          onClick={() => void handleSimulate()}
        >
          {running ? 'Running simulation…' : 'Simulate'}
        </button>
        {runningStage && (
          <div className="text-caption text-accent-cyan">
            {runningStage.detail || `${runningStage.name} stage running`}
          </div>
        )}
        {simError && (
          <div className="border-l-2 border-accent-red pl-2 text-caption text-accent-red">{simError}</div>
        )}
        <div className="flex flex-col items-center justify-center gap-2 text-center mt-8">
          <MapPin className="text-text-disabled" size={32} />
          <p className="text-caption text-text-secondary">
            Run a simulation to see ranked suspects and match scores here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4 flex-1 overflow-y-auto">
      <div className="text-secondary text-caption">
        Post-simulation ranked shortlist. MatchScore reflects drift-fit; AnomalyScore is carried from the shortlist.
      </div>
      {results.ranking.map((suspect) => {
        const anomaly = anomalyByMmsi.get(suspect.mmsi);
        return (
          <div key={suspect.mmsi} className="bg-panel-raised rounded-lg p-3 relative">
            <span className="absolute top-2 left-2 px-2 py-0.5 rounded bg-ocean text-caption text-text-secondary">
              #{suspect.rank}
            </span>
            <div className="flex items-center justify-between pl-12">
              <div>
                <div className="text-display font-medium">{suspect.vessel_name}</div>
                <div className="text-caption text-text-secondary">MMSI {suspect.mmsi}</div>
              </div>
              <ConfidenceBadge value={suspect.match_score} label="Match" />
            </div>
            <div className="flex gap-3 mt-2 text-caption text-text-secondary">
              <span>IoU {suspect.iou.toFixed(2)}</span>
              <span>Centroid {suspect.centroid_distance_km.toFixed(1)} km</span>
              <span>Orientation {suspect.orientation_match.toFixed(2)}</span>
            </div>
            {anomaly && (
              <>
                <div className="border-t border-border-subtle mt-2 pt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-caption text-text-secondary">AnomalyScore (from shortlist)</span>
                    <ConfidenceBadge value={anomaly.anomaly_score} label="Anomaly" />
                  </div>
                  <div className="flex gap-3 mt-1 text-caption text-text-secondary">
                    <span>Blackout {anomaly.anomaly_breakdown.blackout.toFixed(2)}</span>
                    <span>Speed {anomaly.anomaly_breakdown.speed.toFixed(2)}</span>
                    <span>Route {anomaly.anomaly_breakdown.route.toFixed(2)}</span>
                    <span>Draft {anomaly.anomaly_breakdown.draft.toFixed(2)}</span>
                  </div>
                </div>
              </>
            )}
            <button
              type="button"
              className="mt-2 text-caption text-accent-cyan hover:underline"
              onClick={() => setSplitView(!splitView)}
            >
              View on map
            </button>
          </div>
        );
      })}
      <div className="flex flex-col gap-2">
        <button
          type="button"
          className="w-full py-2 rounded-md text-body bg-panel-raised hover:bg-panel"
          onClick={() => setSplitView(!splitView)}
        >
          View simulated map
        </button>
        <button
          type="button"
          className="w-full py-2 rounded-md text-body bg-panel-raised hover:bg-panel"
          onClick={() => {
            /* download handled via getResults export in full phase */
          }}
        >
          Download
        </button>
      </div>
    </div>
  );
}
