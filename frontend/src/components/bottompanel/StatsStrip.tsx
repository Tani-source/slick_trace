import { usePipelineStore } from '../../state/pipelineStore';

export default function StatsStrip() {
  const pipelineStatus = usePipelineStore((s) => s.pipelineStatus);
  const stage1 = pipelineStatus?.stages?.[1]; // Stage 1 (Backward Drift)
  
  return (
    <div className="flex items-center bg-panel-raised p-4 border-subtle">
      <div className="text-caption text-primary">
        Stage 1: Backward Drift
      </div>
      <div className="flex items-center gap-4">
        <div>
          <span className="text-caption">Stage Status:</span>
          <span className="text-primary">{stage1?.status || 'Pending'}</span>
        </div>
        <div className="text-caption text-secondary">
          {stage1?.detail || 'Not started'}
        </div>
      </div>
    </div>
  );