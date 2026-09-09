import { usePipelineStore } from '../../state/pipelineStore';

export default function BottomPanel() {
  const {
    pipelineStatus,
    slick,
    shortlist,
    results,
    runningPipeline,
    runId,
    startPipeline,
    startSimulation,
  } = usePipelineStore();

  const simulated = !!(
    pipelineStatus &&
    Array.isArray(pipelineStatus.stages) &&
    pipelineStatus.stages.find((s) => s.name === 'drift_simulation' && s.status === 'done')
  );
  const simulating = runningPipeline;

  // Read top score from Stage 6 results if available, otherwise Stage 4 shortlist anomaly score
  const topScore =
    results && results.ranking.length > 0
      ? `MATCH: ${results.ranking[0].match_score > 0 && results.ranking[0].match_score < 0.01 ? '<0.01' : (results.ranking[0].match_score ?? 0).toFixed(2)}`
      : shortlist && shortlist.candidates.length > 0
      ? `ANOMALY: ${(shortlist.candidates[0].anomaly_score ?? 0).toFixed(2)}`
      : '—';

  const particles = simulated ? '5,000' : '—';

  const handleAction = () => {
    if (!shortlist || shortlist.candidates.length === 0) {
      // Stage 0-4 not completed yet -> launch initial pipeline
      startPipeline();
    } else {
      // Stage 0-4 done -> launch Stage 5-6 drift simulation
      startSimulation();
    }
  };

  return (
    <div className="st-bottom">
      <div className="st-stat-strip">
        <div className="st-row">
          <span className="st-k">SLICK AREA</span>
          <span className="st-v">
            {slick ? (
              <>
                {(slick.area_km2 == null || isNaN(slick.area_km2))
                  ? '—'
                  : `${slick.area_km2.toFixed(1)} km²`}
                {slick.fallback_used && (
                  <span style={{ color: 'var(--rust-bright)', fontSize: '9px', marginLeft: '6px' }}>
                    (⚠ Synthetic Polygon)
                  </span>
                )}
              </>
            ) : (
              '—'
            )}
          </span>
        </div>
        <div className="st-row">
          <span className="st-k">ORIGIN WINDOW</span>
          <span className="st-v brass">
            {slick ? (
              <>
                {(slick.age_estimate_hours == null || isNaN(slick.age_estimate_hours))
                  ? '—'
                  : `${slick.age_estimate_hours.toFixed(1)}h`}
              </>
            ) : (
              '—'
            )}
          </span>
        </div>
        <div className="st-row">
          <span className="st-k">CANDIDATES</span>
          <span className="st-v">{shortlist ? shortlist.candidates.length : '—'}</span>
        </div>
      </div>

      <div className="st-timeline-area">
        <div className="st-timeline-top">
          <div className="st-playctrls">
            <button className="st-playbtn">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            </button>
            <div className="st-timeline-range">
              <b>08:00</b> 24 OCT — <b>18:30</b> 25 OCT
            </div>
          </div>
          <div className="st-granularity">
            <span>1H</span>
            <span className="on">6H</span>
            <span>24H</span>
          </div>
        </div>
        <div className="st-waveform">
          <svg preserveAspectRatio="none" viewBox="0 0 100 34">
            <path
              d="M0,34 L0,20 Q5,10 10,25 T20,15 T30,28 T40,12 T50,22 T60,8 T70,25 T80,18 T90,26 T100,10 L100,34 Z"
              fill="var(--panel-2)"
              stroke="var(--line-strong)"
              strokeWidth="1"
            />
            <path
              d="M0,34 L0,20 Q5,10 10,25 T20,15 T30,28 T40,12 T50,22 T60,8 T70,25 T80,18 T90,26 T100,10 L100,34 Z"
              fill="rgba(193,81,47,0.15)"
              stroke="var(--rust-bright)"
              strokeWidth="1.5"
              clipPath="inset(0 60% 0 0)"
            />
          </svg>
        </div>
        <div className="st-day-ticks">
          <span>24 Oct</span>
          <span>12:00</span>
          <span>25 Oct</span>
          <span>12:00</span>
          <span>26 Oct</span>
        </div>
      </div>

      <div className="st-bottom-actions">
        <div
          className="st-row"
          style={{
            display: 'flex',
            gap: '8px',
            fontSize: '10px',
            color: 'var(--text-faint)',
            marginBottom: '4px',
          }}
        >
          <span>
            PTCLS: <b style={{ color: 'var(--text)', fontWeight: 500 }}>{particles}</b>
          </span>
          <span>
            TOP SCORE: <b style={{ color: 'var(--brass-bright)', fontWeight: 500 }}>{topScore}</b>
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="st-btn" disabled={!simulated}>
            Export PDF
          </button>
          <button
            className="st-btn primary"
            disabled={simulating || !runId}
            onClick={handleAction}
          >
            {simulating
              ? 'Processing Pipeline...'
              : !shortlist || shortlist.candidates.length === 0
              ? 'Run Analysis Pipeline (0–4)'
              : simulated
              ? 'Re-run Simulation (5–6)'
              : 'Simulate Drift (5–6)'}
          </button>
        </div>
      </div>
    </div>
  );
}
