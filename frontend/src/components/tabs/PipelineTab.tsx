import { usePipelineStore } from '../../state/pipelineStore';

const STAGE_DESCRIPTIONS: Record<string, { title: string; desc: string }> = {
  perception: {
    title: '1. SAR Perception & Segmentation',
    desc: 'Isolating candidate oil slick polygons from Sentinel-1 SAR imagery using U-Net neural segmentation.',
  },
  backward_drift: {
    title: '2. Backward Drift Hindcast',
    desc: 'Reversing ocean currents and wind forcing to back-calculate the origin spatiotemporal envelope.',
  },
  ais_ingestion: {
    title: '3. AIS Trajectory Ingestion',
    desc: 'Collation and indexing of historical vessel trajectories within the origin spatiotemporal window.',
  },
  candidate_filtering: {
    title: '4. Candidate Corridor Filtering',
    desc: 'Spatial-temporal intersection of vessel tracks against the backward drift envelope and corridor bounds.',
  },
  anomaly_scoring: {
    title: '5. Behavioral Anomaly Scoring',
    desc: 'Evaluating AIS gaps/blackout, anomalous speed reductions, course divergence, and draft variations.',
  },
  drift_simulation: {
    title: '6. Forward Drift Simulation',
    desc: 'Simulating forward advection, Fay spreading, and weathering physics (OpenOil) for top candidates.',
  },
  verification_matching: {
    title: '7. Verification & Attribution',
    desc: 'Matching simulated slick footprints with observed SAR morphology (IoU, centroid distance, elongation).',
  },
};

export default function PipelineTab({
  hasData,
  simulating,
  simProgress,
  simulated: _simulated,
}: {
  hasData: boolean;
  simulating: boolean;
  simProgress: number;
  simulated: boolean;
}) {
  const { pipelineStatus, runningPipeline, pollError } = usePipelineStore();

  if (!hasData) {
    return (
      <div className="st-empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <p>Awaiting input datasets. Upload SAR imagery, AIS tracks, wind, and current data to enable the pipeline.</p>
      </div>
    );
  }

  const stages = pipelineStatus ? pipelineStatus.stages : [];
  const failedStage = stages.find((s) => s.status === 'failed');

  return (
    <div className="st-content-scroll">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div>
          <h2 className="st-pagehead">Pipeline Execution</h2>
          <p className="st-pagesub">Monitor the automated multi-stage oil spill source attribution workflow.</p>
        </div>
        {runningPipeline && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--brass-bright)' }}>
            <span className="st-dot active" style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: 'var(--brass-bright)', animation: 'pulse 1.5s infinite' }}></span>
            Executing Pipeline Stages…
          </div>
        )}
      </div>

      {(pollError || failedStage) && (
        <div
          style={{
            background: 'rgba(193,81,47,0.15)',
            border: '1px solid var(--rust-bright)',
            color: 'var(--rust-bright)',
            padding: '12px 16px',
            borderRadius: '6px',
            marginBottom: '16px',
            fontSize: '12px',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>⚠ Pipeline Execution Alert</div>
          <div>{pollError || `Stage '${failedStage?.name}' failed: ${failedStage?.detail || 'Execution error'}`}</div>
        </div>
      )}

      <div className="st-stage-list">
        {stages.map((stage, i) => {
          const meta = STAGE_DESCRIPTIONS[stage.name] || {
            title: `${i + 1}. ${stage.name.replace(/_/g, ' ').toUpperCase()}`,
            desc: stage.detail || '',
          };
          const isDone = stage.status === 'done';
          const isFailed = stage.status === 'failed';
          const isActive = stage.status === 'running' || (stage.name === 'drift_simulation' && simulating);
          const percent = isFailed
            ? 0
            : stage.name === 'drift_simulation' && simulating
            ? Math.round(simProgress)
            : isDone
            ? 100
            : stage.progress_pct || null;

          return (
            <div
              key={stage.name}
              className={`st-stage ${isDone ? 'done' : isFailed ? 'failed' : isActive ? 'active' : ''}`}
            >
              <div className="st-stage-num">{isFailed ? '✕' : isDone ? '✓' : i + 1}</div>
              <div>
                <div className="st-stage-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>{meta.title}</span>
                  {isFailed && (
                    <span style={{ fontSize: '9px', background: 'var(--rust-bright)', color: '#fff', padding: '1px 6px', borderRadius: '3px', textTransform: 'uppercase' }}>
                      Failed
                    </span>
                  )}
                  {isActive && (
                    <span style={{ fontSize: '9px', background: 'var(--brass)', color: '#000', padding: '1px 6px', borderRadius: '3px', textTransform: 'uppercase', fontWeight: 600 }}>
                      Running
                    </span>
                  )}
                </div>
                <div className="st-stage-desc">{meta.desc}</div>
                {stage.detail && (
                  <div
                    style={{
                      marginTop: '6px',
                      fontSize: '11px',
                      color: isFailed ? 'var(--rust-bright)' : 'var(--chart-teal-bright)',
                      fontFamily: 'monospace',
                    }}
                  >
                    {isFailed ? `⚠ Error: ${stage.detail}` : `ℹ ${stage.detail}`}
                  </div>
                )}
              </div>
              <div className="st-stage-right">
                <div className="st-stage-pct">
                  {isFailed ? 'FAILED' : percent !== null ? `${percent}%` : 'PENDING'}
                </div>
                <div className="st-progress-track">
                  <div className="st-progress-fill" style={{ width: `${percent || (isFailed ? 100 : 0)}%` }}></div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
