import { useUiStore } from '../../state/uiStore';
import { usePipelineStore } from '../../state/pipelineStore';

export default function TopBar() {
  const activeTab = useUiStore((s) => s.activeTab);
  const status = usePipelineStore((s) => s.status);
  
  const crumbName = activeTab.charAt(0).toUpperCase() + activeTab.slice(1);
  const isOk = status === 'completed';

  return (
    <div className="st-topbar">
      <div className="st-crumb">
        Workspace / <b>{crumbName}</b>
      </div>
      <div className="st-case-pill">
        <span className={`st-dot ${isOk ? 'ok' : ''}`}></span>
        {status === 'running' ? 'Pipeline active' : status === 'completed' ? 'Case resolved' : 'Draft case'}
      </div>
    </div>
  );
}
