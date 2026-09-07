import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import { usePipelineStore } from '../../../state/pipelineStore';
import { useUIStore } from '../../../state/uiStore';

export default function ReleasePointLayer() {
  const map = useMap();
  const shortlist = usePipelineStore((s) => s.shortlist);
  const layerVisible = useUIStore((s) => s.layerToggles.releasePoints);

  useEffect(() => {
    if (!shortlist || !layerVisible) return;
    const layers: L.Layer[] = [];
    shortlist.candidates.forEach((c) => {
      c.candidate_release_points.forEach((pt) => {
        const marker = L.circleMarker([pt.lat, pt.lon], {
          radius: 4,
          color: '#38BDF8',
          fillColor: '#38BDF8',
          fillOpacity: 0.6,
        }).addTo(map);
        layers.push(marker);
      });
    });
    return () => {
      layers.forEach((l) => map.removeLayer(l));
    };
  }, [map, shortlist, layerVisible]);

  return null;
}
