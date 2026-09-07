import React from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useUiStore } from './state/uiStore';

const STAGES = [
  'perception',
  'ais_ingestion',
  'candidate_filtering',
  'anomaly_scoring',
  'drift_simulation',
  'verification_matching',
];

const STAGE_LABELS: Record<string, string> = {
  perception: 'SAR Perception',
  ais_ingestion: 'AIS Ingestion',
  candidate_filtering: 'Candidate Filter',
  anomaly_scoring: 'Anomaly Scoring',
  drift_simulation: 'Drift Simulation',
  verification_matching: 'Verification & Match',
};

function TabInput() {
  return (
    <div style={panelBody}>
      <h2 style={panelTitle}>Data Inputs</h2>
      <p style={muted}>Upload the four required datasets to begin attribution analysis.</p>
      <div style={uploadCard}>
        <div style={uploadRow}>
          <UploadItem label="SAR Slick Image" hint=".tif / .tiff GRD SAR image" />
          <UploadItem label="Slick Polygon" hint=".geojson polygon over the slick" />
          <UploadItem label="AIS Data" hint=".csv MarineCadastre format" />
          <UploadItem label="Ocean Forcing" hint=".nc ERA5 / CMEMS wind+current" />
        </div>
      </div>
      <button style={btnPrimary} onClick={() => alert('Run pipeline (not yet wired)')}>
        ▶  Run Pipeline
      </button>
    </div>
  );
}

function UploadItem({ label, hint }: { label: string; hint: string }) {
  return (
    <div style={uploadItem}>
      <div style={uploadItemHeader}>{label}</div>
      <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 6 }}>{hint}</div>
      <label style={uploadBtn}>
        Choose File
        <input type="file" style={{ display: 'none' }} />
      </label>
    </div>
  );
}

function TabPipeline() {
  return (
    <div style={panelBody}>
      <h2 style={panelTitle}>Pipeline Execution</h2>
      <p style={muted}>Pipeline will run once datasets are uploaded. Progress updates every 2s.</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
        {STAGES.map((s) => (
          <StageRow key={s} name={s} status="pending" pct={0} detail="Waiting to start" />
        ))}
      </div>
    </div>
  );
}

function StageRow({ name, status, pct, detail }: { name: string; status: string; pct: number; detail: string }) {
  const statusColor: Record<string, string> = {
    pending: '#4b5563',
    running: '#3b82f6',
    done: '#10b981',
    failed: '#ef4444',
  };
  return (
    <div style={{ background: '#111827', borderRadius: 8, padding: '10px 14px', border: '1px solid #1f2937' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: '#e5e7eb' }}>{STAGE_LABELS[name] ?? name}</span>
        <span style={{ fontSize: 11, color: statusColor[status] ?? '#6b7280', textTransform: 'uppercase', letterSpacing: 1 }}>{status}</span>
      </div>
      <div style={{ height: 4, background: '#1f2937', borderRadius: 2 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: statusColor[status] ?? '#3b82f6', borderRadius: 2, transition: 'width 0.4s' }} />
      </div>
      <div style={{ fontSize: 11, color: '#6b7280', marginTop: 5 }}>{detail}</div>
    </div>
  );
}

function TabShortlist() {
  return (
    <div style={panelBody}>
      <h2 style={panelTitle}>Candidate Shortlist</h2>
      <p style={muted}>Vessels that were near the spill origin within the release time window. Run the pipeline to populate.</p>
      <div style={{ ...emptyState }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>🚢</div>
        <div style={{ color: '#4b5563' }}>No candidates yet</div>
      </div>
      <button style={{ ...btnPrimary, background: '#6b21a8', marginTop: 12, opacity: 0.5, cursor: 'not-allowed' }} title="Run pipeline and drift simulation first">
        ⚡  Run Drift Simulation
      </button>
    </div>
  );
}

function TabResults() {
  return (
    <div style={panelBody}>
      <h2 style={panelTitle}>Final Attribution</h2>
      <p style={muted}>Ranked suspect vessels with Anomaly Score and Match Score shown separately.</p>
      <div style={emptyState}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>🏆</div>
        <div style={{ color: '#4b5563' }}>No results yet</div>
      </div>
    </div>
  );
}

const TABS = [
  { id: 'input' as const, label: 'Inputs', icon: '📡' },
  { id: 'pipeline' as const, label: 'Pipeline', icon: '⚙️' },
  { id: 'shortlist' as const, label: 'Shortlist', icon: '🔍' },
  { id: 'results' as const, label: 'Results', icon: '🏆' },
];

export default function App() {
  const { activeTab, setActiveTab, sidebarOpen, setSidebarOpen } = useUiStore();

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: '#070b14', fontFamily: 'Inter, sans-serif' }}>

      {/* ── Icon rail (always visible) ── */}
      <div style={iconRail}>
        <div style={{ padding: '16px 0', borderBottom: '1px solid #1f2937', textAlign: 'center' }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: '#38bdf8', letterSpacing: -0.5 }}>ST</span>
        </div>
        {TABS.map(tab => (
          <button
            key={tab.id}
            title={tab.label}
            onClick={() => { setActiveTab(tab.id); if (!sidebarOpen) setSidebarOpen(true); }}
            style={{
              ...iconBtn,
              background: activeTab === tab.id && sidebarOpen ? 'rgba(56,189,248,0.12)' : 'transparent',
              borderRight: activeTab === tab.id && sidebarOpen ? '2px solid #38bdf8' : '2px solid transparent',
            }}
          >
            <span style={{ fontSize: 18 }}>{tab.icon}</span>
          </button>
        ))}
      </div>

      {/* ── Collapsible detail panel ── */}
      <div style={{
        width: sidebarOpen ? 320 : 0,
        minWidth: sidebarOpen ? 320 : 0,
        overflow: 'hidden',
        transition: 'width 0.25s cubic-bezier(.4,0,.2,1)',
        background: 'rgba(13,20,36,0.97)',
        backdropFilter: 'blur(12px)',
        borderRight: '1px solid #1f2937',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid #1f2937', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', letterSpacing: -0.3 }}>SlickTrace</span>
          <button onClick={() => setSidebarOpen(false)} style={{ ...ghostBtn }}>✕</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {activeTab === 'input' && <TabInput />}
          {activeTab === 'pipeline' && <TabPipeline />}
          {activeTab === 'shortlist' && <TabShortlist />}
          {activeTab === 'results' && <TabResults />}
        </div>
      </div>

      {/* ── Map ── */}
      <div style={{ flex: 1, position: 'relative' }}>
        <MapContainer
          center={[29.0, -89.0]}
          zoom={7}
          zoomControl={false}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; OSM contributors &copy; CARTO'
          />
        </MapContainer>

        {/* Sidebar toggle when closed */}
        {!sidebarOpen && (
          <button
            onClick={() => setSidebarOpen(true)}
            style={{ position: 'absolute', top: 14, left: 14, zIndex: 500, ...ghostBtn, background: 'rgba(13,20,36,0.9)', border: '1px solid #1f2937', padding: '6px 12px', fontSize: 13 }}
          >
            ☰ SlickTrace
          </button>
        )}

        {/* Map tool strip */}
        <div style={{ position: 'absolute', right: 14, top: 14, zIndex: 500, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {[['L', 'Layers'], ['+', 'Zoom in'], ['-', 'Zoom out']].map(([icon, tip]) => (
            <button key={tip} title={tip} style={mapToolBtn}>{icon}</button>
          ))}
        </div>

        {/* Bottom status bar */}
        <div style={statusBar}>
          <span style={{ color: '#6b7280', fontSize: 11, fontFamily: 'monospace' }}>
            STATUS: <span style={{ color: '#34d399' }}>IDLE</span>
          </span>
          <span style={{ color: '#374151', fontSize: 11 }}>Gulf of Mexico · Nov 2023 · SlickTrace v0.1</span>
        </div>
      </div>
    </div>
  );
}

// ── Styles ──
const panelBody: React.CSSProperties = { padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: 12 };
const panelTitle: React.CSSProperties = { margin: 0, fontSize: 17, fontWeight: 700, color: '#f1f5f9' };
const muted: React.CSSProperties = { margin: 0, fontSize: 12, color: '#6b7280', lineHeight: 1.5 };
const emptyState: React.CSSProperties = { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 120, background: '#0d1424', borderRadius: 8, border: '1px dashed #1f2937' };
const uploadCard: React.CSSProperties = { background: '#0d1424', borderRadius: 10, padding: 14, border: '1px solid #1f2937' };
const uploadRow: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 10 };
const uploadItem: React.CSSProperties = { background: '#111827', borderRadius: 7, padding: '10px 12px' };
const uploadItemHeader: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#e5e7eb', marginBottom: 3 };
const uploadBtn: React.CSSProperties = { display: 'inline-block', padding: '4px 10px', background: '#1f2937', border: '1px solid #374151', borderRadius: 5, fontSize: 11, color: '#9ca3af', cursor: 'pointer' };
const btnPrimary: React.CSSProperties = { padding: '10px 16px', background: 'linear-gradient(135deg,#0ea5e9,#6366f1)', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, fontSize: 13, cursor: 'pointer', letterSpacing: 0.3 };
const iconRail: React.CSSProperties = { width: 52, minWidth: 52, background: '#0d1424', borderRight: '1px solid #1f2937', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, paddingTop: 0 };
const iconBtn: React.CSSProperties = { width: '100%', padding: '14px 0', border: 'none', cursor: 'pointer', color: '#9ca3af', transition: 'background 0.15s, color 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const ghostBtn: React.CSSProperties = { background: 'transparent', border: 'none', color: '#6b7280', cursor: 'pointer', padding: '4px 8px', borderRadius: 5, fontSize: 13, transition: 'color 0.15s' };
const mapToolBtn: React.CSSProperties = { width: 32, height: 32, background: 'rgba(13,20,36,0.85)', border: '1px solid #1f2937', borderRadius: 6, color: '#9ca3af', fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const statusBar: React.CSSProperties = { position: 'absolute', bottom: 0, left: 0, right: 0, height: 36, background: 'rgba(7,11,20,0.92)', borderTop: '1px solid #1f2937', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px' };
