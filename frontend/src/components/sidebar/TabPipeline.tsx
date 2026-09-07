import { usePipelineStore } from '../../state/pipelineStore';
import { useUIStore } from '../../../state/uiStore';
import { STAGE_DESCRIPTIONS, STAGE_LABELS, STAGE_ICONS, StageName, StageStatus, PipelineStage } from '../../types/contracts';

const ALL_STAGES: StageName[] = [
  'perception',
  'ais_ingestion',
  'candidate_filtering',
  'anomaly_scoring',
  'drift_simulation',
  'verification_matching',
];

export default function TabPipeline() {
  const pipelineStatus = usePipelineStore((s) => s.pipelineStatus);
  const slick = usePipelineStore((s) => s.slick);

  const getStageStatus = (name: StageName): PipelineStage | null => {
    return pipelineStatus?.stages.find((s) => s.name === name) || null;
  };

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto flex-1">
      <div className="text-secondary text-caption mb-2">
        Real-time pipeline execution status.
      </div>

      <div className="flex flex-col gap-3">
        {ALL_STAGES.map((stageName) => {
          const liveStage = getStageStatus(stageName);
          const status = liveStage?.status || 'pending';
          const detail = liveStage?.detail || (pipelineStatus ? 'Waiting...' : 'Upload data first.');
          
          return (
            <div key={stageName} className="bg-panel-raised rounded-lg p-3 flex flex-col gap-2 border-l-2" style={{ borderLeftColor: getStatusColor(status) }}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span>{STAGE_ICONS[stageName]}</span>
                  <span className="text-body font-medium">{STAGE_LABELS[stageName]}</span>
                </div>
                <span className="text-caption px-2 py-0.5 rounded-full" style={{ backgroundColor: getStatusBg(status), color: getStatusColor(status) }}>
                  {status.toUpperCase()}
                </span>
              </div>
              <p className="text-caption text-text-secondary">{STAGE_DESCRIPTIONS[stageName]}</p>
              
              <div className="text-caption mt-1" style={{ color: getStatusColor(status) }}>
                {detail}
              </div>

              {stageName === 'perception' && status === 'done' && slick && (
                <div className="mt-2 p-2 bg-panel rounded border border-border-subtle flex flex-col gap-1 text-caption text-text-secondary">
                  <div><strong>Area:</strong> {slick.area_km2.toFixed(2)} km²</div>
                  <div><strong>Age Estimate:</strong> {slick.age_estimate_hours}h</div>
                  <div><strong>Weathering Validity:</strong> {slick.weathering_validity ? <span className="text-accent-green">Valid (≤72h)</span> : <span className="text-accent-red">Invalid (&gt;72h)</span>}</div>
                  <div><strong>Shape (Elongation):</strong> {slick.elongation_ratio.toFixed(2)}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function getStatusColor(status: StageStatus) {
  switch (status) {
    case 'running': return 'var(--color-accent-teal)';
    case 'done': return 'var(--color-accent-green)';
    case 'failed': return 'var(--color-accent-red)';
    default: return 'var(--color-text-disabled)';
  }
}

function getStatusBg(status: StageStatus) {
  switch (status) {
    case 'running': return 'rgba(45, 212, 191, 0.1)';
    case 'done': return 'rgba(52, 211, 153, 0.1)';
    case 'failed': return 'rgba(248, 113, 113, 0.1)';
    default: return 'rgba(255, 255, 255, 0.05)';
  }
}