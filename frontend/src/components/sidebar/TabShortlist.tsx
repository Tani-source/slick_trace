import { usePipelineStore } from '../../state/pipelineStore';
import { MapPin } from 'lucide-react';

export default function TabShortlist() {
  const shortlist = usePipelineStore((s) => s.shortlist);
  const candidates = shortlist?.candidates ?? [];

  if (candidates.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 text-center p-4 flex-1">
        <MapPin className="text-text-disabled" size={32} />
        <p className="text-caption text-text-secondary">
          These are AIS-flagged candidates prior to drift simulation. See Results for final confidence-scored rankings.
        </p>
        <p className="text-caption text-text-secondary">
          A shortlist will appear here once the anomaly-scoring stage completes for an uploaded case.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4 flex-1 overflow-y-auto">
      <div className="text-caption text-accent-amber border-l-2 border-accent-amber pl-2">
        These are AIS-flagged candidates prior to drift simulation. See Results for final confidence-scored rankings.
      </div>
      {candidates.map((c) => (
        <div key={c.mmsi} className="bg-panel-raised rounded-lg p-3 flex flex-col gap-2">
          <div>
            <div className="text-display font-medium">{c.vessel_name}</div>
            <div className="text-caption text-text-secondary">
              MMSI {c.mmsi} · {c.vessel_type} · {c.flag} · {c.operator}
            </div>
          </div>
          <div className="text-caption text-text-secondary">
            Destination: {c.destination || 'n/a'} · Pos {c.position_at_event.lat.toFixed(3)},{' '}
            {c.position_at_event.lon.toFixed(3)}
          </div>
          <div className="text-caption text-text-secondary">AnomalyScore {(c.anomaly_score * 100).toFixed(0)}%</div>
          <div className="flex gap-3 text-caption text-text-secondary">
            <span>Blackout {c.anomaly_breakdown.blackout.toFixed(2)}</span>
            <span>Speed {c.anomaly_breakdown.speed.toFixed(2)}</span>
            <span>Route {c.anomaly_breakdown.route.toFixed(2)}</span>
            <span>Draft {c.anomaly_breakdown.draft.toFixed(2)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
