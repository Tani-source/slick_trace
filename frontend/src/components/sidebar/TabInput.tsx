import { useState } from 'react';
import type { DatasetType, DatasetInfo, ProvenanceTag } from '../../types/contracts';
import { usePipelineStore } from '../../state/pipelineStore';
import { UploadCloud } from 'lucide-react';

const DATASET_DEFS: {
  type: DatasetType;
  title: string;
  description: string;
  fileHint: string;
}[] = [
  {
    type: 'wind',
    title: 'Wind',
    description: '10m wind components (u/v), NetCDF or CSV. Used as forcing input for the drift simulation.',
    fileHint: 'NetCDF, CSV',
  },
  {
    type: 'current',
    title: 'Ocean Current',
    description: 'Ocean current components (uo/vo), NetCDF or CSV. Drives slick transport.',
    fileHint: 'NetCDF, CSV',
  },
  {
    type: 'sar',
    title: 'SAR Image',
    description: 'Sentinel-1 SAR crop (or .npy/.png), plus optional scene bounds. Primary slick detection source.',
    fileHint: 'PNG, JPEG, TIFF, .npy',
  },
  {
    type: 'ais',
    title: 'AIS',
    description: 'Vessel-track CSV with timestamp, MMSI, and position columns. Used for suspect attribution.',
    fileHint: 'CSV',
  },
];

const PROVENANCE_OPTIONS: { value: ProvenanceTag; label: string }[] = [
  { value: 'real', label: 'Real' },
  { value: 'synthetic', label: 'Synthetic' },
  { value: 'illustrative', label: 'Illustrative' },
];

function StatusPill({ info }: { info: DatasetInfo }) {
  if (info.status === 'uploaded') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-caption bg-accent-green/20 text-accent-green">Uploaded ✓</span>;
  }
  if (info.status === 'invalid' && info.reason) {
    return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-caption bg-accent-red/20 text-accent-red">Invalid ⚠</span>;
  }
  return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-caption bg-panel-raised text-text-disabled">Not uploaded</span>;
}

export default function TabInput() {
  const datasets = usePipelineStore((s) => s.datasets);
  const upload = usePipelineStore((s) => s.upload);
  const allUploaded = Object.values(datasets).every((d) => d.status === 'uploaded');

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto flex-1">
      <div className="text-secondary text-caption">
        Upload the four input datasets for the current case. The pipeline runs on the SAR image and AIS tracks,
        forced by wind and ocean current.
      </div>

      {DATASET_DEFS.map((def) => {
        const info = datasets[def.type];
        return (
          <div key={def.type} className="bg-panel-raised rounded-lg p-3 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-body font-medium">{def.title}</span>
                <span className="text-caption text-text-secondary">{def.fileHint}</span>
              </div>
              <StatusPill info={info} />
            </div>
            <p className="text-caption text-text-secondary">{def.description}</p>
            <ProvenancePicker type={def.type} fileHint={def.fileHint} onUpload={upload} />
            {info.status === 'invalid' && info.reason && (
              <div className="border-l-2 border-accent-red pl-2 text-caption text-accent-red">
                {info.reason}
              </div>
            )}
            {(info.status === 'uploaded') && (
              <div className="text-caption text-text-secondary">
                {info.provenance && <span className="mr-2">Tag: {info.provenance}</span>}
                {info.file_name && <span className="mr-2">{info.file_name}</span>}
                {info.bbox && <span>bbox: [{info.bbox.join(', ')}]</span>}
                {info.date_range && <span className="ml-2">window: {info.date_range.join(' → ')}</span>}
              </div>
            )}
          </div>
        );
      })}

      <button
        type="button"
        disabled={!allUploaded}
        title={allUploaded ? '' : 'Upload all 4 datasets before running the pipeline.'}
        className="w-full py-3 rounded-md text-display font-medium transition"
        style={
          allUploaded
            ? { background: 'var(--color-accent-teal)', color: '#0B1E3D' }
            : { background: 'var(--color-panel-raised)', color: 'var(--color-text-disabled)' }
        }
        onClick={() => void usePipelineStore.getState().startPipeline()}
      >
        Run pipeline
      </button>
    </div>
  );
}

function ProvenancePicker({
  type,
  onUpload,
}: {
  type: DatasetType;
  fileHint: string;
  onUpload: (type: DatasetType, file: File, prov: string) => Promise<void>;
}) {
  const [prov, setProv] = useState<ProvenanceTag>('illustrative');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await onUpload(type, file, prov);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Upload failed';
      if (msg.includes('missing timestamp') || msg.includes('file empty') || msg.includes('not recognized') || msg.includes('CRS')) {
        setError(msg);
      } else {
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <select
          value={prov}
          onChange={(e) => setProv(e.target.value as ProvenanceTag)}
          className="bg-panel text-text-primary border border-border-subtle rounded px-2 py-1 text-caption"
        >
          {PROVENANCE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <label className="flex-1 flex items-center justify-center gap-2 border border-dashed border-border-subtle rounded-md py-3 cursor-pointer hover:bg-panel text-text-secondary text-caption">
          <UploadCloud size={16} />
          {busy ? 'Uploading…' : 'Drop or choose *.csv / *.png / *.npy'}
          <input
            type="file"
            className="hidden"
            accept={fileHint}
            onChange={(e) => void handleFile(e.target.files?.[0])}
          />
        </label>
      </div>
      {error && <div className="border-l-2 border-accent-red pl-2 text-caption text-accent-red">{error}</div>}
    </div>
  );
}
