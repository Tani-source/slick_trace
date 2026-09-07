/**
 * StatsStrip.tsx — Live glanceable stats strip in the bottom panel.
 * design.md §6. Mirrors Tab 3 pipeline state, condensed.
 */

import React from "react";
import { usePipelineStore } from "../../state/pipelineStore";

function StatItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center px-4">
      <span className="text-label" style={{ fontSize: "10px" }}>{label}</span>
      <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "4px" }}>
        {value}
      </span>
    </div>
  );
}

export default function StatsStrip() {
  const { pipelineStatus, slickPolygon, originEnvelope, shortlist, runId } = usePipelineStore();

  const getStageStatus = (name: string) =>
    pipelineStatus?.stages.find((s) => s.name === name)?.status ?? "pending";

  const runningStage = pipelineStatus?.stages.find((s) => s.status === "running");
  const doneCount = pipelineStatus?.stages.filter((s) => s.status === "done").length ?? 0;

  return (
    <div
      className="flex items-center justify-around h-full overflow-x-auto"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <StatItem
        label="RUN ID"
        value={runId ? runId.slice(0, 8) + "…" : "—"}
      />
      <div style={{ width: "1px", height: "32px", background: "var(--border-subtle)" }} />
      <StatItem
        label="STAGES DONE"
        value={pipelineStatus ? `${doneCount} / 6` : "—"}
      />
      <div style={{ width: "1px", height: "32px", background: "var(--border-subtle)" }} />
      <StatItem
        label="SLICK AREA"
        value={
          slickPolygon ? (
            <>
              {slickPolygon.area_km2.toFixed(1)} km²
              {slickPolygon.fallback_used && (
                <span style={{ color: "var(--accent-red)", fontSize: "10px", marginLeft: "4px" }}>
                  (⚠ Synthetic Polygon)
                </span>
              )}
            </>
          ) : (
            "—"
          )
        }
      />
      <div style={{ width: "1px", height: "32px", background: "var(--border-subtle)" }} />
      <StatItem
        label="ORIGIN WINDOW"
        value={
          originEnvelope ? (
            <>
              {originEnvelope.time_window_hours.toFixed(1)}h
              {originEnvelope.fallback_used && (
                <span style={{ color: "var(--accent-red)", fontSize: "10px", marginLeft: "4px" }}>
                  (⚠ Numpy Fallback)
                </span>
              )}
            </>
          ) : (
            "—"
          )
        }
      />
      <div style={{ width: "1px", height: "32px", background: "var(--border-subtle)" }} />
      <StatItem
        label="CANDIDATES"
        value={shortlist ? String(shortlist.candidates.length) : "—"}
      />
      <div style={{ width: "1px", height: "32px", background: "var(--border-subtle)" }} />
      <StatItem
        label="CURRENT STAGE"
        value={runningStage ? runningStage.name.replace(/_/g, " ") : (doneCount === 6 ? "Complete" : "—")}
      />
    </div>
  );
}
