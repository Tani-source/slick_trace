import { useEffect, useState } from 'react';
import { useMap } from 'react-leaflet';
import { Layer } from 'react-leaflet';
import { usePipelineStore } from '../../../state/pipelineStore';
import { useUIStore } from '../../../state/uiStore';

export default function MapCanvas() {
  const map = useMap();
  const { pipelineStatus, layerToggles } = usePipelineStore();
  const { activeTab } = useUIStore();
  
  const [originEnvelope, setOriginEnvelope] = useState<L.LatLngBounds | null>(null);
  const [simulationRunning, setSimulationActive] = useState(false);

  // Load origin envelope when Stage 1 completes
  useEffect(() => {
    if (pipelineStatus?.stages?.[1]?.status === 'done') {
      // Get origin envelope from Stage 1 output
      const originData = pipelineStatus?.stages?.[1]?.detail?.match(/origin region: (.+)/)?.[1];
      if (originData) {
        // Parse origin data (simplified for demo)
        const originBbox = pipelineStatus?.stages?.[0]?.detail?.match(/bbox:\s*\[([\d.-]+), ([-\d.]+), ([-\d.]+), ([-\d.]+)\]/)?.[1];
        if (bbox) {
          const [minLat, minLon, maxLat, maxLon] = bbox.split(',').map(parseFloat);
          const originBounds = L.latLngBounds([minLat, minLon], [maxLat, maxLon]);
          setOriginEnvelope(origin);
          setSimulationActive(true);
        }
      }
    }
  }, [pipelineStatus]);

  return (
    <div className="map-container">
      <MapCanvas />
      {originEnvelope && (
        <LayerGroup>
          <Polygon
            positions={originEnvelope.getLatLngs()}
            color="var(--color-accent-cyan)"
            fillColor="rgba(56, 188, 255, 0.2)"
            className="simulated-drift-layer"
          />
        </LayerGroup>
      )}
    </div>
  );
}