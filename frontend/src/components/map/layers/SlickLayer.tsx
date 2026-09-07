/**
 * SlickLayer.tsx — Renders the detected slick polygon on the Leaflet map.
 * design.md §5.1: accent-teal outline + low-opacity fill.
 * Phase 1 deliverable: appears once Stage 0 is complete.
 */

import React from "react";
import { Polygon, Tooltip } from "react-leaflet";
import type { SlickPolygon } from "../../../types/contracts";

interface Props {
  slick: SlickPolygon;
}

export default function SlickLayer({ slick }: Props) {
  // Leaflet expects [lat, lon] tuples — already in that format per contract
  const positions = slick.polygon as [number, number][];

  return (
    <Polygon
      positions={positions}
      pathOptions={{
        color: "#2dd4bf",       // --accent-teal
        weight: 2,
        opacity: 0.9,
        fillColor: "#2dd4bf",
        fillOpacity: 0.12,
      }}
    >
      <Tooltip sticky>
        <div style={{ fontSize: "12px", color: "#0b1e3d" }}>
          <strong>Observed Slick</strong>
          <br />
          Area: {slick.area_km2.toFixed(2)} km²
          <br />
          Age est.: {slick.age_estimate_hours.toFixed(1)} h
          {!slick.weathering_validity && (
            <><br /><span style={{ color: "#f04438" }}>⚠ Age &gt;72h — low confidence</span></>
          )}
          {slick.fallback_used && (
            <><br /><span style={{ color: "#f04438" }}>⚠ U-Net Fallback</span></>
          )}
        </div>
      </Tooltip>
    </Polygon>
  );
}
