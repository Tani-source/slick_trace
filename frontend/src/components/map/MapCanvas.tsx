/**
 * MapCanvas.tsx — Always-visible Leaflet map with layer composition.
 * design.md §5. Map is shared state, not owned by any tab (architecture.md §2.3).
 */

import React, { useEffect } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { usePipelineStore } from "../../state/pipelineStore";
import { useUiStore } from "../../state/uiStore";
import SlickLayer from "./layers/SlickLayer";
import OriginEnvelopeLayer from "./layers/OriginEnvelopeLayer";
import AISTrackLayer from "./layers/AISTrackLayer";
import ReleasePointLayer from "./layers/ReleasePointLayer";
import SimulatedDriftLayer from "./layers/SimulatedDriftLayer";
import DarkShipLayer from "./layers/DarkShipLayer";

// Gulf of Mexico demo region center
const DEFAULT_CENTER: [number, number] = [27.5, -90.0];
const DEFAULT_ZOOM = 7;

function MapController() {
  const map = useMap();
  const { slick: slickPolygon } = usePipelineStore();

  useEffect(() => {
    if (slickPolygon?.bbox) {
      const [minLat, minLon, maxLat, maxLon] = slickPolygon.bbox;
      map.fitBounds([
        [minLat, minLon],
        [maxLat, maxLon],
      ], { padding: [40, 40] });
    }
  }, [slickPolygon, map]);

  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return;
    const container = map.getContainer();
    let resizeTimer: number;
    const resizeObserver = new ResizeObserver(() => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        map.invalidateSize();
      }, 50);
    });
    resizeObserver.observe(container);
    return () => {
      resizeObserver.disconnect();
      window.clearTimeout(resizeTimer);
    };
  }, [map]);

  return null;
}

export default function MapCanvas() {
  const { slick: slickPolygon, shortlist, originEnvelope, simulatedFootprints, connectionLost } = usePipelineStore();
  const { activeLayers, darkShipEnabled } = useUiStore();

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        style={{ height: "100%", width: "100%" }}
        zoomControl={false}
        attributionControl={false}
      >
        {/* Basemap — Esri Dark Gray gives a dark aesthetic without requiring an API key */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
          attribution='Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'
          maxZoom={16}
        />

        <MapController />

        {/* Layer: observed slick polygon */}
        {activeLayers.has("slick") && slickPolygon && (
          <SlickLayer slick={slickPolygon} />
        )}

        {/* Layer: origin envelope */}
        {activeLayers.has("originEnvelope") && originEnvelope && (
          <OriginEnvelopeLayer envelope={originEnvelope} />
        )}

        {/* Layer: AIS candidate tracks */}
        {activeLayers.has("aisTracks") && shortlist && (
          <AISTrackLayer candidates={shortlist.candidates} />
        )}

        {/* Layer: release points */}
        {activeLayers.has("releasePoints") && shortlist && (
          <ReleasePointLayer candidates={shortlist.candidates} />
        )}

        {/* Layer: simulated drift footprints */}
        {activeLayers.has("driftFootprints") && simulatedFootprints && (
          <SimulatedDriftLayer footprints={simulatedFootprints} />
        )}

        {/* Prototype: Dark Ship Detections */}
        {darkShipEnabled && <DarkShipLayer />}
      </MapContainer>

      {/* Empty state overlay when no data loaded */}
      {!slickPolygon && (
        <div
          className="st-empty-state"
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 500,
            pointerEvents: 'none',
            background: 'rgba(8, 20, 32, 0.4)'
          }}
        >
          <div style={{
            background: 'var(--panel)',
            border: '1px solid var(--line-strong)',
            backdropFilter: 'blur(6px)',
            padding: '16px 24px',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            Upload datasets and run the pipeline — the slick polygon, AIS tracks, and drift layers will appear here.
          </div>
        </div>
      )}

      {/* Network Error Overlay (design.md §7.2) */}
      {connectionLost && (
        <div
          className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-2 px-4 py-2 rounded-lg pointer-events-none"
          style={{
            background: "var(--accent-amber)",
            color: "#000",
            zIndex: 1000,
            boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
          }}
        >
          <span className="font-bold text-sm">Connection lost, retrying…</span>
        </div>
      )}
    </div>
  );
}
