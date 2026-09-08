/**
 * OriginEnvelopeLayer.tsx — Renders the backward drift origin envelope.
 */

import { Polygon, Tooltip } from "react-leaflet";

interface Props {
  envelope: {
    polygon: [number, number][];
    area_km2: number;
    time_window_hours: number;
    fallback_used: boolean;
  };
}

export default function OriginEnvelopeLayer({ envelope }: Props) {
  return (
    <Polygon
      positions={envelope.polygon}
      pathOptions={{
        color: "#f5a524",       // --accent-amber
        weight: 2,
        opacity: 0.9,
        fillColor: "#f5a524",
        fillOpacity: 0.1,
        dashArray: "5,5",
      }}
    >
      <Tooltip sticky>
        <div style={{ fontSize: "12px", color: "#0b1e3d" }}>
          <strong>Origin Envelope</strong>
          <br />
          Area: {(envelope.area_km2 ?? 0).toFixed(1)} km²
          <br />
          Window: {(envelope.time_window_hours ?? 0).toFixed(1)}h
          {envelope.fallback_used && (
            <><br /><span style={{ color: "#f04438" }}>⚠ Numpy Fallback</span></>
          )}
        </div>
      </Tooltip>
    </Polygon>
  );
}
