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
  const { slickPolygon } = usePipelineStore();

  useEffect(() => {
    if (slickPolygon?.bbox) {
      const [minLat, minLon, maxLat, maxLon] = slickPolygon.bbox;
      map.fitBounds([
        [minLat, minLon],
        [maxLat, maxLon],
      ], { padding: [40, 40] });
    }
  }, [slickPolygon, map]);

  return null;
}

export default function MapCanvas() {
  const { slickPolygon, shortlist, originEnvelope, simulatedFootprints, connectionLost } = usePipelineStore();
  const { activeLayers, darkShipEnabled } = useUiStore();

  return (
    <div className="relative flex-1 h-full">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        style={{ height: "100%", width: "100%" }}
        zoomControl={false}
        attributionControl={false}
      >
        {/* Basemap — CartoDB Dark Matter gives the --bg-ocean aesthetic */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          maxZoom={19}
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
          className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
          style={{ zIndex: 500 }}
        >
          <div
            className="flex flex-col items-center gap-2 px-6 py-4 rounded-lg"
            style={{
              background: "rgba(18,42,82,0.85)",
              border: "1px solid var(--border-subtle)",
              backdropFilter: "blur(6px)",
            }}
          >
            <p className="text-caption text-center" style={{ color: "var(--text-secondary)" }}>
              Upload datasets and run the pipeline — the slick polygon, AIS tracks, and drift layers will appear here.
            </p>
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
