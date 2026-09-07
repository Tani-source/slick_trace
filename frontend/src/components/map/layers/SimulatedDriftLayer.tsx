import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import { usePipelineStore } from '../../../state/pipelineStore';
import { useUIStore } from '../../../state/uiStore';

export default function SimulatedDriftLayer() {
  const map = useMap();
  const slick = usePipelineStore((s) => s.slick);
  const results = usePipelineStore((s) => s.results);
  const layerVisible = useUIStore((s) => s.layerToggles.simulatedDrift);

  useEffect(() => {
    if (!results || results.ranking.length === 0 || !slick || !layerVisible) return;
    const layer = L.polygon(slick.polygon, {
      color: '#38BDF8',
      weight: 2,
      fillColor: '#38BDF8',
      fillOpacity: 0.1,
    }).addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, slick, results, layerVisible]);

  return null;
}
