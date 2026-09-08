/**
 * DarkShipLayer.tsx — Prototype layer for Dark-Ship Detection (Phase 5).
 * Renders an offline-generated marker.
 */

import React, { useEffect, useState } from "react";
import { CircleMarker, Tooltip } from "react-leaflet";
import { getPrototypeDarkShip } from "../../../api/client";
import type { DarkShipResult } from "../../../types/contracts";

export default function DarkShipLayer() {
  const [data, setData] = useState<DarkShipResult | null>(null);

  useEffect(() => {
    let active = true;
    getPrototypeDarkShip().then((res) => {
      if (active) setData(res);
    }).catch(console.error);
    return () => { active = false; };
  }, []);

  if (!data) return null;

  return (
    <>
      {(data.detected_vessels ?? []).map((v, i) => (
        <CircleMarker
          key={i}
          center={[v.lat, v.lon]}
          radius={8}
          pathOptions={{
            color: "#f04438", // Danger red
            fillColor: "#f04438",
            fillOpacity: 0.6,
            weight: 2,
          }}
        >
          <Tooltip sticky>
            <div style={{ fontSize: "12px", color: "#0b1e3d" }}>
              <span style={{ color: "#f04438", fontWeight: "bold" }}>
                {data.label}
              </span>
              <br />
              <strong>Dark-Ship Detected</strong>
              <br />
              Confidence: {(v.confidence * 100).toFixed(0)}%
              <br />
              Note: {v.note}
              <br />
              <span style={{ fontSize: "10px", color: "#666" }}>
                Method: {data.method}
              </span>
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  );
}
