/**
 * TabShortlist.tsx — Tab 4: Pre-simulation AIS-flagged candidates.
 * design.md §4.6. Read-only cards. Fixed caption at top distinguishing from Tab 1.
 * AnomalyScore and its breakdown always visible here (never collapsed, rules.md §3.3).
 */

import React from "react";
import { MapPin, Flag, Anchor } from "lucide-react";
import { usePipelineStore } from "../../state/pipelineStore";
import { useUiStore } from "../../state/uiStore";
import type { Candidate } from "../../types/contracts";

function scoreColor(score: number): string {
  if (score >= 0.7) return "var(--accent-green)";
  if (score >= 0.4) return "var(--accent-amber)";
  return "var(--accent-red)";
}

function AnomalyBadge({ score }: { score: number }) {
  return (
    <span
      className="badge"
      style={{
        background: `rgba(0,0,0,0.2)`,
        color: scoreColor(score),
        border: `1px solid ${scoreColor(score)}55`,
        fontSize: "13px",
        fontWeight: 700,
        padding: "3px 10px",
      }}
    >
      {(score * 100).toFixed(0)}%
    </span>
  );
}

function CandidateCard({ candidate }: { candidate: Candidate }) {
  const { setHighlightedMmsi } = useUiStore();
  const bd = candidate.anomaly_breakdown;

  return (
    <div className="card" style={{ marginBottom: "10px" }}>
      {/* Header */}
      <div className="flex items-start justify-between mb-1">
        <div>
          <p className="text-display" style={{ fontSize: "15px" }}>
            {candidate.vessel_name}
          </p>
          <p className="text-label">MMSI {candidate.mmsi}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="text-label" style={{ color: "var(--text-disabled)" }}>ANOMALY</span>
          <AnomalyBadge score={candidate.anomaly_score} />
        </div>
      </div>

      {/* Vessel meta */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 mb-2">
        <span className="text-caption flex items-center gap-1">
          <Anchor size={10} /> {candidate.vessel_type}
        </span>
        <span className="text-caption flex items-center gap-1">
          <Flag size={10} /> {candidate.flag}
        </span>
        <span className="text-caption">{candidate.operator}</span>
        <span className="text-caption">→ {candidate.destination}</span>
      </div>

      {/* Position at event */}
      <div
        className="flex items-center gap-2 px-2 py-1 rounded mb-2"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)" }}
      >
        <MapPin size={11} style={{ color: "var(--accent-cyan)", flexShrink: 0 }} />
        <span className="text-caption">
          {candidate.position_at_event.lat.toFixed(4)}°N,{" "}
          {candidate.position_at_event.lon.toFixed(4)}°E at{" "}
          {new Date(candidate.position_at_event.time).toUTCString()}
        </span>
      </div>

      {/* Anomaly sub-scores */}
      <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "8px", marginTop: "4px" }}>
        <p className="text-label mb-1.5">Anomaly Breakdown</p>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          {(
            [
              ["Blackout", bd.blackout, false],
              ["Speed", bd.speed, false],
              ["Route", bd.route, true],
              ["Draft", bd.draft, true],
            ] as [string, number, boolean][]
          ).map(([label, val, isMocked]) => (
            <div key={label} className="flex items-center justify-between">
              <span className="text-caption flex items-center gap-1">
                {label}
                {isMocked && <span className="text-[var(--accent-red)] text-[9px]">(Mocked)</span>}
              </span>
              <span
                className="text-caption font-semibold"
                style={{ color: scoreColor(val) }}
              >
                {(val * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* View on map */}
      <button
        className="btn btn-secondary mt-2"
        style={{ fontSize: "12px", padding: "5px 10px" }}
        onClick={() => setHighlightedMmsi(candidate.mmsi)}
      >
        View on map
      </button>
    </div>
  );
}

export default function TabShortlist() {
  const { shortlist } = usePipelineStore();

  return (
    <div style={{ padding: "16px" }}>
      <h2 className="text-display mb-1">Shortlist</h2>

      {/* Fixed distinguishing caption — design.md §4.6, rules.md §3.3 spirit */}
      <p
        className="text-caption mb-4 px-3 py-2 rounded"
        style={{
          background: "rgba(56,189,248,0.07)",
          borderLeft: "3px solid var(--accent-cyan)",
          color: "var(--accent-cyan)",
          fontStyle: "italic",
        }}
      >
        These are AIS-flagged candidates prior to drift simulation. See Results for final confidence-scored rankings.
      </p>

      {!shortlist || shortlist.candidates.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-8">
          <div
            style={{
              width: 40, height: 40, borderRadius: "50%",
              background: "rgba(45,212,191,0.08)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            <Anchor size={20} style={{ color: "var(--accent-teal)" }} />
          </div>
          <p className="text-caption text-center">
            No shortlist yet. Upload datasets and run the pipeline to generate AIS candidates.
          </p>
        </div>
      ) : (
        shortlist.candidates.map((c) => (
          <CandidateCard key={c.mmsi} candidate={c} />
        ))
      )}
    </div>
  );
}
