import React from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

export const MapCanvas: React.FC = () => {
  return (
    <div className="h-full w-full relative z-0">
      <MapContainer 
        center={[29.0, -89.0]} 
        zoom={7} 
        style={{ height: '100%', width: '100%', background: '#111827' }}
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
      </MapContainer>
    </div>
  );
};
