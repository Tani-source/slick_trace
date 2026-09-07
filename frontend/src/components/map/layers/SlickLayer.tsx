import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import { usePipelineStore } from '../../../state/pipelineStore';
import { useUIStore } from '../../../state/uiStore';

export default function SlickLayer() {
  const map = useMap();
  const slick = usePipelineStore((s) => s.slick);
  const layerVisible = useUIStore((s) => s.layerToggles.slick);

  useEffect(() => {
    if (!slick || !layerVisible) return;
    const layer = L.polygon(slick.polygon, {
      color: '#2DD4BF',
      weight: 2,
      fillColor: '#2DD4BF',
      fillOpacity: 0.15,
    }).addTo(map);
    map.fitBounds(layer.getBounds(), { padding: [40, 40] });
    return () => {
      map.removeLayer(layer);
    };
  }, [map, slick, layerVisible]);

  return null;
}
