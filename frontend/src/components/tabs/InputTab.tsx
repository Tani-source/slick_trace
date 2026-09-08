import { useRef, useState } from 'react';
import { usePipelineStore } from '../../state/pipelineStore';
import type { DatasetType } from '../../types/contracts';

export default function InputTab() {
  const { datasets, runId, upload, startPipeline, runningPipeline, pipelineStatus } = usePipelineStore();
  const [uploadingType, setUploadingType] = useState<DatasetType | null>(null);
  const [dragOverType, setDragOverType] = useState<DatasetType | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fileInputRefs = {
    sar: useRef<HTMLInputElement>(null),
    ais: useRef<HTMLInputElement>(null),
    wind: useRef<HTMLInputElement>(null),
    current: useRef<HTMLInputElement>(null),
  };

  const datasetList = [
    { type: 'sar' as DatasetType, name: 'SAR Imagery', format: 'GeoTIFF / Sentinel-1', icon: 'M', accept: '.tif,.tiff' },
    { type: 'ais' as DatasetType, name: 'AIS Tracks', format: 'CSV / Spire', icon: 'A', accept: '.csv' },
    { type: 'wind' as DatasetType, name: 'Wind Field', format: 'GRIB / ECMWF / NetCDF', icon: 'W', accept: '.nc,.grb,.grib' },
    { type: 'current' as DatasetType, name: 'Ocean Currents', format: 'NetCDF / HYCOM', icon: 'C', accept: '.nc' },
  ];

  const handleFile = async (type: DatasetType, file: File) => {
    setErrorMsg(null);
    setUploadingType(type);
    try {
      await upload(type, file, 'user_upload');
    } catch (err: any) {
      setErrorMsg(`Failed to upload ${type.toUpperCase()}: ${err?.message || 'Upload failed'}`);
    } finally {
      setUploadingType(null);
    }
  };

  const handleDragOver = (e: React.DragEvent, type: DatasetType) => {
    e.preventDefault();
    setDragOverType(type);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOverType(null);
  };

  const handleDrop = async (e: React.DragEvent, type: DatasetType) => {
    e.preventDefault();
    setDragOverType(null);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      await handleFile(type, file);
    }
  };

  const uploadedCount = Object.values(datasets).filter((d) => d.status === 'uploaded').length;

  return (
    <div className="st-content-scroll">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div>
          <h2 className="st-pagehead">Input Datasets</h2>
          <p className="st-pagesub">
            Upload environmental and vessel tracking data to launch slick perception & origin analysis.
          </p>
        </div>

        <div style={{ textAlign: 'right' }}>
          {runId && (
            <div style={{ fontSize: '11px', color: 'var(--brass-bright)', marginBottom: '6px', fontFamily: 'monospace' }}>
              ACTIVE RUN: <b>{runId}</b>
            </div>
          )}
          <button
            className="st-btn primary"
            disabled={runningPipeline || uploadedCount === 0}
            onClick={() => startPipeline()}
            style={{ padding: '8px 16px', fontSize: '12px' }}
          >
            {runningPipeline ? 'Running Stages 0–4...' : 'Run Analysis Pipeline (Stages 0–4)'}
          </button>
        </div>
      </div>

      {errorMsg && (
        <div style={{ background: 'rgba(193,81,47,0.2)', border: '1px solid var(--rust-bright)', color: 'var(--rust-bright)', padding: '10px 14px', borderRadius: '4px', marginBottom: '16px', fontSize: '12px' }}>
          ⚠ {errorMsg}
        </div>
      )}

      {runningPipeline && pipelineStatus && (
        <div style={{ background: 'var(--panel-2)', border: '1px solid var(--chart-teal)', padding: '12px 16px', borderRadius: '4px', marginBottom: '16px', fontSize: '12px' }}>
          <div style={{ fontWeight: 600, color: 'var(--chart-teal-bright)', marginBottom: '4px' }}>Pipeline Running in Background</div>
          <div style={{ color: 'var(--text-faint)' }}>
            Active Stage: {pipelineStatus.stages.find(s => s.status === 'running')?.name || 'processing'}
          </div>
        </div>
      )}

      <div className="st-grid4">
        {datasetList.map((ds) => {
          const info = datasets[ds.type];
          const isUploaded = info.status === 'uploaded';
          const isUploading = uploadingType === ds.type;
          const isDragging = dragOverType === ds.type;

          return (
            <div key={ds.type} className="st-dataset-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <input
                type="file"
                ref={fileInputRefs[ds.type]}
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    handleFile(ds.type, e.target.files[0]);
                  }
                }}
              />

              <div>
                <div className="st-ds-head">
                  <div className="st-ds-icon">{ds.icon}</div>
                  <div>
                    <div className="st-ds-name">{ds.name}</div>
                    <div className="st-ds-format">{ds.format}</div>
                  </div>
                </div>

                {!isUploaded ? (
                  <div
                    className={`st-dropzone ${isDragging ? 'dragging' : ''}`}
                    style={{
                      border: isDragging ? '2px dashed var(--chart-teal-bright)' : '1px dashed var(--line-strong)',
                      background: isDragging ? 'rgba(0,180,180,0.1)' : 'var(--panel-2)',
                      padding: '24px 12px',
                      textAlign: 'center',
                      cursor: 'pointer',
                      borderRadius: '4px',
                      marginTop: '12px',
                      transition: 'all 0.2s ease',
                    }}
                    onDragOver={(e) => handleDragOver(e, ds.type)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, ds.type)}
                    onClick={() => fileInputRefs[ds.type].current?.click()}
                  >
                    {isUploading ? (
                      <span style={{ color: 'var(--brass-bright)' }}>Uploading file...</span>
                    ) : (
                      <>
                        <span style={{ fontWeight: 500, color: 'var(--text)' }}>Drop file here</span>
                        <br />
                        <span style={{ fontSize: '10px', color: 'var(--text-faint)' }}>or click to browse ({ds.accept})</span>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="st-ds-meta" style={{ marginTop: '12px' }}>
                    <div className="st-kv">
                      <span>Status</span>
                      <span className="st-ds-status uploaded">
                        <span className="st-d"></span> Ready
                      </span>
                    </div>
                    <div className="st-kv">
                      <span>File Name</span>
                      <span style={{ fontFamily: 'monospace', fontSize: '11px', color: 'var(--text)' }}>{info.file_name || 'Uploaded'}</span>
                    </div>
                    <div className="st-kv">
                      <span>Provenance</span>
                      <span className="st-tag tanker" style={{ textTransform: 'uppercase', fontSize: '9px' }}>
                        {info.provenance || 'REAL'}
                      </span>
                    </div>
                    <div className="st-kv">
                      <span>Size</span>
                      <span>{info.size_bytes ? `${(info.size_bytes / 1024).toFixed(1)} KB` : 'N/A'}</span>
                    </div>
                    {info.bbox && (
                      <div className="st-kv">
                        <span>Coverage</span>
                        <span style={{ fontSize: '10px' }}>
                          {info.bbox[0].toFixed(1)}°, {info.bbox[1].toFixed(1)}°
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {isUploaded && (
                <button
                  className="st-btn"
                  style={{ marginTop: '12px', fontSize: '10px', width: '100%' }}
                  onClick={() => fileInputRefs[ds.type].current?.click()}
                >
                  Replace File
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
