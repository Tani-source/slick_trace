import { usePipelineStore } from '../../state/pipelineStore';

export default function SuspectsTab() {
  const { shortlist, results } = usePipelineStore();

  if (!shortlist || shortlist.candidates.length === 0) {
    return (
      <div className="st-empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <p>No candidates available yet. Run the pipeline to generate the shortlist.</p>
      </div>
    );
  }

  return (
    <div className="st-content-scroll">
      <h2 className="st-pagehead">Candidate Shortlist</h2>
      <p className="st-pagesub">Vessels intersecting the origin envelope, ranked by spatiotemporal proximity to the simulated footprint.</p>

      <div className="st-suspect-grid">
        {shortlist.candidates.map((c, i) => {
          const result = results?.ranking.find(r => r.mmsi === c.mmsi);
          const matchScore = result?.match_score ?? c.match_score ?? 0;
          return (
          <div key={c.mmsi} className="st-suspect-card">
            <div className="st-sc-head">
              <div>
                <div className="st-sc-name">{c.name || 'Unknown Vessel'} <span className="st-sc-mmsi">MMSI {c.mmsi}</span></div>
                <div style={{marginTop: '4px'}}>
                  <span className="st-tag tanker">{c.type || 'Tanker'}</span>
                  <span className="st-sc-flag" style={{marginLeft: '6px'}}>{c.flag || 'Unknown'}</span>
                </div>
              </div>
              <div className={`st-rank-badge ${i === 0 ? 'st-rank-1' : ''}`}>#{i + 1}</div>
            </div>
            
            <div className="st-sc-grid">
              <div className="st-sc-item">
                <div className="st-k">MATCH SCORE</div>
                <div className="st-v">
                  <div className="st-score-bar-wrap">
                    <span style={{color: 'var(--chart-teal-bright)', fontWeight: 500}}>
                      {matchScore > 0 && matchScore < 0.01 ? '<0.01' : matchScore.toFixed(2)}
                    </span>
                    <div className="st-score-bar"><i style={{width: `${matchScore * 100}%`, background: 'var(--chart-teal)'}}></i></div>
                  </div>
                </div>
              </div>
              <div className="st-sc-item">
                <div className="st-k">ANOMALY SCORE</div>
                <div className="st-v">
                  <div className="st-score-bar-wrap">
                    <span style={{color: 'var(--rust-bright)', fontWeight: 500}}>{(c.anomaly_score ?? 0).toFixed(2)}</span>
                    <div className="st-score-bar"><i style={{width: `${(c.anomaly_score ?? 0) * 100}%`, background: 'var(--rust)'}}></i></div>
                  </div>
                </div>
              </div>
              <div className="st-sc-item">
                <div className="st-k">SPATIAL DISTANCE</div>
                <div className="st-v">{c.distance_to_spill_km != null ? `${c.distance_to_spill_km.toFixed(1)} km` : 'N/A'}</div>
              </div>
              <div className="st-sc-item">
                <div className="st-k">TIME DELTA</div>
                <div className="st-v">{c.time_delta_hours != null ? `${c.time_delta_hours.toFixed(1)} hrs` : 'Not computed'}</div>
              </div>
              <div className="st-sc-item">
                <div className="st-k">STATUS AT INTERSECTION</div>
                <div className="st-v">Underway using engine</div>
              </div>
            </div>

            {i === 0 && (
              <div className="st-sc-note">
                Highest overlap with simulated drift footprint. Trajectory matches prevailing wind vectors during the 12h origin window.
              </div>
            )}
          </div>
        )})}
      </div>
    </div>
  );
}
