import { usePipelineStore } from '../../state/pipelineStore';
import MapCanvas from '../map/MapCanvas';

export default function OutputTab() {
  const { pipelineStatus, shortlist, results } = usePipelineStore();
  const simulated = !!(pipelineStatus && Array.isArray(pipelineStatus.stages) && pipelineStatus.stages.find(s => s.name === 'drift_simulation' && s.status === 'done'));

  return (
    <div className={`st-view ${simulated ? 'split' : ''}`}>
      <div className="st-mapwrap primary">
        <div className="st-maptitle">ORIGINAL SATELLITE EXTENT</div>
        <MapCanvas />
        <div className="st-coordbar">
          <span>13°16'18"N 80°20'44"E</span>
          <span>EPSG:4326</span>
        </div>
      </div>
      
      <div className="st-mapwrap secondary">
        <div className="st-maptitle">SIMULATED FORECAST (T+48H)</div>
        <MapCanvas />
        <div className="st-coordbar">
          <span>13°16'18"N 80°20'44"E</span>
          <span>EPSG:4326</span>
        </div>
      </div>

      <div className="st-toolrail">
        <div className="st-tool zoomgroup">
          <div className="st-zbtn">+</div>
          <div className="st-zdivider"></div>
          <div className="st-zbtn">-</div>
        </div>
        <div className="st-tool">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>
        </div>
        <div className="st-tool">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"/></svg>
        </div>
      </div>
      
      {simulated && shortlist && (
        <div className="absolute bottom-16 left-6 right-6 bg-panel border border-border-subtle rounded-md shadow-lg overflow-hidden z-10 p-4">
          <h3 className="st-pagehead" style={{fontSize: '14px', marginBottom: '8px'}}>Results Table</h3>
          <div className="overflow-auto max-h-40">
             <table className="st-table">
               <thead>
                 <tr>
                   <th>RANK</th>
                   <th>MMSI</th>
                   <th>MATCH SCORE</th>
                   <th>ANOMALY SCORE</th>
                 </tr>
               </thead>
               <tbody>
                 {shortlist.candidates.slice(0, 5).map((c, i) => {
                   const result = results?.ranking.find(r => r.mmsi === c.mmsi);
                   const matchScore = result?.match_score ?? c.match_score ?? 0;
                   return (
                   <tr key={c.mmsi}>
                     <td>{i + 1}</td>
                     <td>{c.mmsi}</td>
                     <td style={{color: 'var(--chart-teal-bright)', fontWeight: 500}}>
                       {matchScore > 0 && matchScore < 0.01 ? '<0.01' : matchScore.toFixed(2)}
                     </td>
                     <td style={{color: 'var(--rust-bright)', fontWeight: 500}}>{(c.anomaly_score ?? 0).toFixed(2)}</td>
                   </tr>
                 )})}
               </tbody>
             </table>
          </div>
        </div>
      )}
    </div>
  );
}
