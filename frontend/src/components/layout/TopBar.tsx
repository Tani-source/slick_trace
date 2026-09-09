import { useUiStore } from '../../state/uiStore';
import { usePipelineStore } from '../../state/pipelineStore';

export default function TopBar() {
  const activeTab = useUiStore((s) => s.activeTab);
  const runningPipeline = usePipelineStore((s) => s.runningPipeline);
  const pipelineStatus = usePipelineStore((s) => s.pipelineStatus);
  const results = usePipelineStore((s) => s.results);

  const hasFailed = !!pipelineStatus?.stages?.some((s) => s.status === 'failed');
  const isResolved = results !== null;
  const isOk = !hasFailed && (isResolved || (pipelineStatus?.stages?.length ? pipelineStatus.stages.every((s) => s.status === 'done') : false));

  const crumbName = activeTab.charAt(0).toUpperCase() + activeTab.slice(1);

  return (
    <div className="st-topbar">
      <div className="st-crumb">
        Workspace / <b>{crumbName}</b>
      </div>
      <div className="st-case-pill">
        <span className={`st-dot ${isOk ? 'ok' : hasFailed ? 'failed' : ''}`}></span>
        {runningPipeline
          ? 'Pipeline active'
          : hasFailed
          ? 'Pipeline error'
          : isResolved
          ? 'Case resolved'
          : 'Draft case'}
      </div>
    </div>
  );
}
