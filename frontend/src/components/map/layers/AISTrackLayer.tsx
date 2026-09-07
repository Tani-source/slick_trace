import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import { usePipelineStore } from '../../../state/pipelineStore';
import { useUIStore } from '../../../state/uiStore';

export default function AISTrackLayer() {
  const map = useMap();
  const shortlist = usePipelineStore((s) => s.shortlist);
  const layerVisible = useUIStore((s) => s.layerToggles.aisTracks);

  useEffect(() => {
    if (!shortlist || !layerVisible) return;
    const layers: L.Layer[] = [];
    shortlist.candidates.forEach((c) => {
      const color =
        c.anomaly_score >= 0.7
          ? '#22C55E'
          : c.anomaly_score >= 0.4
            ? '#F5A524'
            : '#F04438';
      const marker = L.circleMarker([c.position_at_event.lat, c.position_at_event.lon], {
        radius: 5,
        color,
        fillColor: color,
        fillOpacity: 0.7,
      }).addTo(map);
      layers.push(marker);
    });
    return () => {
      layers.forEach((l) => map.removeLayer(l));
    };
  }, [map, shortlist, layerVisible]);

  return null;
}
