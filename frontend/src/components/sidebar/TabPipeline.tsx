import { usePipelineStore } from '../../state/pipelineStore';
import { useUIStore } from '../../../state/uiStore';
import { StageName, StageStatus } from '../../types/contracts';

export default function TabPipeline() {
  const pipelineStatus = usePipelineStore((s) => s.pipelineStatus);
  const activeTab = useUIStore((s) => s.activeTab);
  const layerToggles = useUIStore((s) => s.layerToggles);

  return (
    <div className="pipeline-tab">
      <div className="pipeline-header">
        <span className="tab-title">Pipeline</span>
      </div>
      
      <div className="stages-container">
        {pipelineStatus?.stages?.map((stage, index) => (
          <div key={index} className="stage-row">
            <span className="stage-name">{stage.name}</span>
            <span className="stage-status">{stage.status}</span>
            <span className="stage-detail">{stage.detail}</span>
          </div>
        )}
      </div>
    </div>
  );
}