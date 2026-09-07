/**
 * TabInput.tsx — Tab 2: Dataset upload cards.
 * design.md §4.4. Four upload cards: Wind → Ocean Current → SAR Image → AIS.
 * All disabled-button states carry tooltip explaining the precondition (rules.md §2).
 */

import React, { useCallback, useRef, useState } from "react";
import { Wind, Waves, Satellite, Ship, Upload, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import * as api from "../../api/client";
import type { DatasetType, UploadStatus, ProvenanceTag, DatasetUploadResponse } from "../../types/contracts";
import { usePipelineStore } from "../../state/pipelineStore";
import { useUiStore } from "../../state/uiStore";

interface CardState {
  status: UploadStatus;
  filename: string | null;
  reason: string | null;
  bbox: [number, number, number, number] | null;
  fallback_used?: boolean;
  provenance: ProvenanceTag;
  uploading: boolean;
}

const DEFAULT_CARD: CardState = {
  status: "not_uploaded",
  filename: null,
  reason: null,
  bbox: null,
  provenance: "real",
  uploading: false,
};

interface UploadCardConfig {
  type: DatasetType;
  label: string;
  description: string;
  fileHint: string;
  icon: React.ReactNode;
}

const CARDS: UploadCardConfig[] = [
  {
    type: "wind",
    label: "Wind Data",
    description: "10m wind components (u/v), NetCDF or CSV. Used as forcing input for the drift simulation.",
    fileHint: "NetCDF, CSV",
    icon: <Wind size={16} />,
  },
  {
    type: "current",
    label: "Ocean Current",
    description: "CMEMS surface ocean current (u/v components). Drives backward and forward drift models.",
    fileHint: "NetCDF, CSV",
    icon: <Waves size={16} />,
  },
  {
    type: "sar",
    label: "SAR Image",
    description: "Sentinel-1 SAR scene (GeoTIFF or NetCDF). Primary slick detection input.",
    fileHint: "GeoTIFF, NetCDF, PNG",
    icon: <Satellite size={16} />,
  },
  {
    type: "ais",
    label: "AIS Data",
    description: "AIS vessel-position records for the region of interest. Used for candidate filtering and anomaly scoring.",
    fileHint: "CSV, JSON",
    icon: <Ship size={16} />,
  },
];

function StatusBadge({ status, reason }: { status: UploadStatus; reason: string | null }) {
  if (status === "not_uploaded") {
    return (
      <span className="badge badge--disabled">Not uploaded</span>
    );
  }
  if (status === "uploaded") {
    return (
      <span className="badge badge--green">
        <CheckCircle2 size={10} /> Uploaded ✓
      </span>
    );
  }
  return (
    <span className="badge badge--red">
      <AlertCircle size={10} /> Invalid ⚠
    </span>
  );
}

function ProvenancePill({ tag }: { tag: ProvenanceTag }) {
  const color: Record<ProvenanceTag, string> = {
    real: "var(--accent-teal)",
    synthetic: "var(--accent-amber)",
    illustrative: "var(--text-secondary)",
  };
  return (
    <span
      className="text-caption"
      style={{
        background: "rgba(255,255,255,0.05)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-badge)",
        padding: "1px 7px",
        color: color[tag],
        fontSize: "10px",
        fontWeight: 500,
        textTransform: "capitalize",
      }}
    >
      {tag}
    </span>
  );
}

interface UploadCardProps {
  config: UploadCardConfig;
  state: CardState;
  onUpload: (type: DatasetType, file: File) => Promise<void>;
}

function UploadCard({ config, state, onUpload }: UploadCardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleFile = useCallback(
    (file: File) => {
      onUpload(config.type, file);
    },
    [config.type, onUpload]
  );

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="card" style={{ marginBottom: "10px" }}>
      {/* Header row */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2" style={{ color: "var(--accent-teal)" }}>
          {config.icon}
          <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
            {config.label}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {state.status === "uploaded" && (
            <ProvenancePill tag={state.provenance} />
          )}
          {state.uploading ? (
            <Loader2 size={14} className="animate-spin" style={{ color: "var(--accent-cyan)" }} />
          ) : (
            <StatusBadge status={state.status} reason={state.reason} />
          )}
        </div>
      </div>

      {/* Description */}
      <p className="text-caption mb-2">{config.description}</p>
      <p style={{ fontSize: "10px", color: "var(--text-disabled)", marginBottom: "8px" }}>
        {config.fileHint}
      </p>

      {/* Inline rejection reason */}
      {state.status === "invalid" && state.reason && (
        <div
          className="text-caption mb-2 px-2 py-1 rounded"
          style={{
            background: "rgba(240,68,56,0.08)",
            borderLeft: "3px solid var(--accent-red)",
            color: "var(--accent-red)",
          }}
        >
          {state.reason}
        </div>
      )}

      {/* BBox / date range after upload */}
      {state.status === "uploaded" && state.filename && (
        <div className="text-caption" style={{ marginBottom: "8px", color: "var(--text-secondary)" }}>
          <p>
            {state.filename}
            {state.bbox && (
              <> · bbox [{state.bbox.map((v) => v.toFixed(2)).join(", ")}]</>
            )}
          </p>
          {state.fallback_used && (
            <p style={{ color: "var(--accent-red)", fontSize: "10px", marginTop: "2px" }}>
              (⚠ Threshold Segmentation Fallback)
            </p>
          )}
        </div>
      )}

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className="flex flex-col items-center justify-center gap-1 rounded cursor-pointer transition-colors"
        style={{
          border: `1.5px dashed ${dragging ? "var(--accent-teal)" : "var(--border-subtle)"}`,
          background: dragging ? "rgba(45,212,191,0.05)" : "rgba(255,255,255,0.02)",
          padding: "12px",
          borderRadius: "6px",
        }}
      >
        <Upload size={14} style={{ color: "var(--text-secondary)" }} />
        <span className="text-caption">Drop file or click to browse</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}

export default function TabInput() {
  const { runId, setRunId, startPolling } = usePipelineStore();
  const { setActiveTab } = useUiStore();

  const [cards, setCards] = useState<Record<DatasetType, CardState>>({
    wind: { ...DEFAULT_CARD },
    current: { ...DEFAULT_CARD },
    sar: { ...DEFAULT_CARD },
    ais: { ...DEFAULT_CARD },
  });
  const [runError, setRunError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const allUploaded = Object.values(cards).every((c) => c.status === "uploaded");

  const handleUpload = useCallback(
    async (type: DatasetType, file: File) => {
      setCards((prev) => ({
        ...prev,
        [type]: { ...prev[type], uploading: true, reason: null },
      }));

      try {
        // Reuse existing run_id or backend will create one
        const res: DatasetUploadResponse = await api.uploadDataset(type, file, runId ?? undefined);

        // Persist the run_id that came back (first upload creates it)
        if (!runId && res.run_id) {
          setRunId(res.run_id);
        }

        setCards((prev) => ({
          ...prev,
          [type]: {
            status: res.status,
            filename: res.filename,
            reason: res.reason ?? null,
            bbox: res.bbox ?? null,
            fallback_used: res.fallback_used ?? false,
            provenance: res.provenance,
            uploading: false,
          },
        }));
      } catch (err) {
        setCards((prev) => ({
          ...prev,
          [type]: {
            ...prev[type],
            status: "invalid",
            reason: err instanceof api.ApiError ? (err.detail ?? err.message) : "Upload failed — check your connection.",
            uploading: false,
          },
        }));
      }
    },
    [runId, setRunId]
  );

  const handleRunPipeline = async () => {
    if (!runId || !allUploaded) return;
    setRunning(true);
    setRunError(null);
    try {
      await api.runPipeline(runId);
      startPolling();
      setActiveTab("pipeline");
    } catch (err) {
      setRunError(
        err instanceof api.ApiError
          ? (err.detail ?? err.message)
          : "Failed to start pipeline."
      );
    } finally {
      setRunning(false);
    }
  };

  return (
    <div style={{ padding: "16px" }}>
      <h2 className="text-display mb-1">Input</h2>
      <p className="text-caption mb-4">
        Upload the four required datasets, then run the pipeline.
      </p>

      {CARDS.map((cfg) => (
        <UploadCard
          key={cfg.type}
          config={cfg}
          state={cards[cfg.type]}
          onUpload={handleUpload}
        />
      ))}

      {runError && (
        <div
          className="text-caption mb-3 px-3 py-2 rounded"
          style={{
            background: "rgba(240,68,56,0.08)",
            borderLeft: "3px solid var(--accent-red)",
            color: "var(--accent-red)",
          }}
        >
          {runError}
        </div>
      )}

      <div className="relative group">
        <button
          className="btn btn-primary"
          disabled={!allUploaded || running}
          onClick={handleRunPipeline}
          aria-describedby={!allUploaded ? "run-tooltip" : undefined}
        >
          {running ? (
            <><Loader2 size={14} className="animate-spin" /> Starting pipeline…</>
          ) : (
            "Run pipeline"
          )}
        </button>
        {/* Disabled tooltip — rules.md §2: always explain why a button is disabled */}
        {!allUploaded && (
          <div
            id="run-tooltip"
            role="tooltip"
            className="absolute bottom-full left-0 right-0 mb-2 px-3 py-2 rounded text-xs text-center pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity"
            style={{
              background: "var(--bg-panel-raised)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-secondary)",
              zIndex: 50,
            }}
          >
            Upload all 4 datasets first.
          </div>
        )}
      </div>
    </div>
  );
}
