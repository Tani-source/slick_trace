import { usePipelineStore } from '../../state/pipelineStore';

const STAGE_DESCRIPTIONS: Record<string, { title: string; desc: string }> = {
  detect_slick: { title: '1. SAR Segmentation', desc: 'Isolating candidate oil slick polygons from Sentinel-1 imagery.' },
  fetch_ais: { title: '2. AIS Collation', desc: 'Retrieving historical vessel tracks from Spire for the region.' },
  simulate_drift: { title: '3. Hindcast Simulation', desc: 'Reversing ocean currents and wind to estimate the origin window.' },
  match_suspects: { title: '4. Spatiotemporal Matching', desc: 'Intersecting AIS tracks with the origin envelope.' },
  score_candidates: { title: '5. Scoring', desc: 'Ranking candidates based on distance, trajectory, and speed.' },
  generate_report: { title: '6. Report Generation', desc: 'Compiling the final attribution report.' }
};

export default function PipelineTab({ hasData, simulating, simProgress, simulated }: { hasData: boolean, simulating: boolean, simProgress: number, simulated: boolean }) {
  const pipelineStatus = usePipelineStore((s) => s.pipelineStatus);

  if (!hasData) {
    return (
      <div className="st-empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <p>Awaiting input datasets. Upload SAR imagery, AIS tracks, wind, and current data to enable the pipeline.</p>
      </div>
    );
  }

  const stages = pipelineStatus ? pipelineStatus.stages : [];

  return (
    <div className="st-content-scroll">
      <h2 className="st-pagehead">Pipeline Execution</h2>
      <p className="st-pagesub">Monitor the automated attribution workflow.</p>

      <div className="st-stage-list">
        {stages.map((stage, i) => {
          const meta = STAGE_DESCRIPTIONS[stage.name] || { title: stage.name, desc: '' };
          const isDone = stage.status === 'done';
          const isActive = stage.status === 'running' || (stage.name === 'simulate_drift' && simulating);
          const percent = stage.name === 'simulate_drift' && simulating ? Math.round(simProgress) : (isDone ? 100 : null);

          return (
            <div key={stage.name} className={`st-stage ${isDone ? 'done' : isActive ? 'active' : ''}`}>
              <div className="st-stage-num">{i + 1}</div>
              <div>
                <div className="st-stage-title">{meta.title}</div>
                <div className="st-stage-desc">{meta.desc}</div>
              </div>
              <div className="st-stage-right">
                <div className="st-stage-pct">{percent !== null ? `${percent}%` : '—'}</div>
                <div className="st-progress-track">
                  <div className="st-progress-fill" style={{ width: `${percent || 0}%` }}></div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
