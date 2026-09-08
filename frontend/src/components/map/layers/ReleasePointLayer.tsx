import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import { usePipelineStore } from '../../../state/pipelineStore';
import { useUiStore } from '../../../state/uiStore';

export default function ReleasePointLayer() {
  const map = useMap();
  const shortlist = usePipelineStore((s) => s.shortlist);
  const layerVisible = useUiStore((s) => s.activeLayers.has('releasePoints'));

  useEffect(() => {
    if (!shortlist || !layerVisible) return;
    const layers: L.Layer[] = [];
    shortlist.candidates.forEach((c) => {
      // candidate_release_points is optional — not all pipeline runs populate it
      const releasePoints = Array.isArray(c.candidate_release_points) ? c.candidate_release_points : [];
      releasePoints.forEach((pt) => {
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
