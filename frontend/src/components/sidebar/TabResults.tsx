/**
 * TabResults.tsx — Displays the final ranked suspect list (Phase 4).
 * Enforces rules.md §3.3: AnomalyScore and MatchScore are always visible and separate.
 */

import React, { useState, useEffect } from "react";
import { usePipelineStore } from "../../state/pipelineStore";
import { useUiStore } from "../../state/uiStore";
import { simulatePipeline, getExportUrl, getPrototypeOilType } from "../../api/client";
import type { OilTypeResult } from "../../types/contracts";

export default function TabResults() {
  const { shortlist, results, runId, pipelineStatus, simulatedFootprints } = usePipelineStore();
  const { darkShipEnabled, setDarkShipEnabled, oilTypeEnabled, setOilTypeEnabled } = useUiStore();
  const [simulating, setSimulating] = useState(false);
  const [oilData, setOilData] = useState<OilTypeResult | null>(null);

  useEffect(() => {
    if (oilTypeEnabled && !oilData) {
      getPrototypeOilType().then(setOilData).catch(console.error);
    }
  }, [oilTypeEnabled, oilData]);

  const handleSimulate = async () => {
    if (!runId || !shortlist) return;
    setSimulating(true);
    try {
      await simulatePipeline(runId);
      // store will auto-poll and pick up results when done
    } catch (e) {
      console.error(e);
      setSimulating(false);
    }
  };

  const isSimulating =
    simulating &&
    pipelineStatus?.stages.find((s) => s.name === "verification_matching")?.status !== "done";

  return (
    <div className="flex flex-col h-full bg-panel p-4 overflow-y-auto">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-bold text-text-primary">Verification Matching</h2>
        {results && runId && (
          <a
            href={getExportUrl(runId)}
            className="px-3 py-1 bg-[var(--accent-teal)] text-[#0b1e3d] text-sm font-semibold rounded hover:brightness-110 transition"
            download
          >
            Download Report
          </a>
        )}
      </div>

      <p className="text-sm text-text-secondary mb-4">
        Forward-simulate drift from each candidate's release point to compare the resulting footprint against the observed slick.
      </p>

      {!results ? (
        <div className="flex flex-col items-center justify-center py-10 bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg">
          <p className="text-sm text-text-muted mb-4">
            {!shortlist
              ? "Awaiting shortlist to begin simulation."
              : isSimulating
              ? "Running physics simulation..."
              : "Ready to simulate forward drift."}
          </p>
          <button
            onClick={handleSimulate}
            disabled={!shortlist || isSimulating}
            className={`px-4 py-2 rounded font-semibold transition ${
              !shortlist || isSimulating
                ? "bg-[var(--border-subtle)] text-text-muted cursor-not-allowed"
                : "bg-[var(--accent-teal)] text-[#0b1e3d] hover:brightness-110 shadow-lg shadow-[var(--accent-teal)]/20"
            }`}
          >
            {isSimulating ? "Simulating..." : "Run Simulation"}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {results.ranking.map((v) => {
            const cand = shortlist?.candidates.find((c) => c.mmsi === v.mmsi);
            const sim = simulatedFootprints?.simulations.find((s) => s.mmsi === v.mmsi);
            const fallbackUsed = sim?.fallback_used || false;

            return (
              <div key={v.mmsi} className="bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg p-4 shadow-md">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="text-xs font-bold text-[var(--accent-amber)] bg-[var(--accent-amber)]/10 px-2 py-1 rounded mb-1 inline-block">
                      Rank {v.rank}
                    </span>
                    <h3 className="font-bold text-text-primary text-lg">
                      {v.vessel_name || "Unknown"} <span className="text-text-muted font-normal text-sm">({v.mmsi})</span>
                    </h3>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-[var(--accent-teal)]">
                      {(v.match_score * 100).toFixed(0)}%
                    </div>
                    <div className="text-xs text-text-muted uppercase tracking-wider">Match Score</div>
                    {fallbackUsed && (
                      <div className="text-[10px] text-[var(--accent-red)] font-semibold mt-1">
                        ⚠ Numpy Fallback
                      </div>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
                  {/* Match Metrics */}
                  <div className="bg-[var(--panel-bg)] rounded p-2 border border-[var(--border-subtle)]">
                    <h4 className="font-semibold text-text-primary mb-2 border-b border-[var(--border-subtle)] pb-1">
                      Match Metrics
                    </h4>
                    <div className="flex justify-between mb-1">
                      <span className="text-text-secondary">Intersection (IoU):</span>
                      <span className="text-text-primary font-mono">{(v.iou * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between mb-1">
                      <span className="text-text-secondary">Centroid Dist:</span>
                      <span className="text-text-primary font-mono">{v.centroid_distance_km.toFixed(1)} km</span>
                    </div>
                  </div>

                  {/* Anomaly Metrics (Carried over) */}
                  <div className="bg-[var(--panel-bg)] rounded p-2 border border-[var(--border-subtle)]">
                    <h4 className="font-semibold text-text-primary mb-2 border-b border-[var(--border-subtle)] pb-1">
                      AIS Anomaly
                    </h4>
                    <div className="flex justify-between mb-1">
                      <span className="text-text-secondary">Overall Score:</span>
                      <span className="text-[var(--accent-amber)] font-mono font-bold">
                        {cand ? cand.anomaly_score.toFixed(3) : "—"}
                      </span>
                    </div>
                    <div className="flex justify-between mb-1">
                      <span className="text-text-secondary">Blackout gap:</span>
                      <span className="text-text-primary font-mono">
                        {cand ? (cand.anomaly_breakdown.blackout * 100).toFixed(0) : "—"}%
                      </span>
                    </div>
                    <div className="flex justify-between mb-1">
                      <span className="text-text-secondary">Route dev.:</span>
                      <span className="text-text-primary font-mono flex items-center gap-1">
                        {cand ? cand.anomaly_breakdown.route.toFixed(2) : "—"}
                        <span className="text-[var(--accent-red)] text-[9px]">(Mocked)</span>
                      </span>
                    </div>
                    <div className="flex justify-between mb-1">
                      <span className="text-text-secondary">Draft anom.:</span>
                      <span className="text-text-primary font-mono flex items-center gap-1">
                        {cand ? cand.anomaly_breakdown.draft.toFixed(2) : "—"}
                        <span className="text-[var(--accent-red)] text-[9px]">(Mocked)</span>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Prototype Features Section */}
      <div className="mt-8 pt-6 border-t border-[var(--border-subtle)]">
        <div className="mb-4">
          <h3 className="text-lg font-bold text-text-primary mb-1">Advanced Prototypes</h3>
          <p className="text-xs text-[var(--accent-amber)] font-semibold px-2 py-1 bg-[var(--accent-amber)]/10 inline-block rounded">
            Prototype — architecture below
          </p>
        </div>

        <div className="space-y-4">
          {/* Dark Ship Toggle */}
          <div className="flex items-center justify-between p-3 bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg">
            <div>
              <div className="font-semibold text-text-primary text-sm">Dark-Ship Detection</div>
              <div className="text-xs text-text-muted mt-1">Overlay CFAR SAR detections on map</div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={darkShipEnabled}
                onChange={(e) => setDarkShipEnabled(e.target.checked)}
              />
              <div className="w-11 h-6 bg-[var(--border-subtle)] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent-teal)]"></div>
            </label>
          </div>

          {/* Oil Type Toggle */}
          <div className="flex items-center justify-between p-3 bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg">
            <div>
              <div className="font-semibold text-text-primary text-sm">Oil-Type Fingerprinting</div>
              <div className="text-xs text-text-muted mt-1">Classify oil using Sentinel-2</div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={oilTypeEnabled}
                onChange={(e) => setOilTypeEnabled(e.target.checked)}
              />
              <div className="w-11 h-6 bg-[var(--border-subtle)] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent-teal)]"></div>
            </label>
          </div>

          {/* Oil Type Data Display */}
          {oilTypeEnabled && oilData && (
            <div className="p-4 mt-2 bg-[var(--panel-bg)] border border-[var(--accent-teal)]/30 rounded-lg">
              <h4 className="text-sm font-bold text-text-primary border-b border-[var(--border-subtle)] pb-2 mb-2">
                Classification Result
              </h4>
              <div className="grid grid-cols-2 gap-2 text-sm mb-3">
                <div className="text-text-secondary">Type:</div>
                <div className="text-[var(--accent-teal)] font-bold uppercase">{oilData.classified_type}</div>
                
                <div className="text-text-secondary">Confidence:</div>
                <div className="text-text-primary font-mono">{(oilData.confidence * 100).toFixed(0)}%</div>
              </div>
              <div className="text-xs text-text-muted mt-2 border-t border-[var(--border-subtle)] pt-2">
                <span className="font-semibold">Method:</span> {oilData.method}
                <br/>
                <span className="italic mt-1 block">{oilData.note}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
