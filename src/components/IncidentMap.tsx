import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Navigation, MapPin, Target } from 'lucide-react';
import { useDetection } from '@/contexts/DetectionContext';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default marker icon in React Leaflet
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

// Component to handle map movement
const MapController = () => {
    const map = useMap();
    const { selectedAlert } = useDetection();

    useEffect(() => {
        if (selectedAlert) {
            map.flyTo([selectedAlert.lat, selectedAlert.lon], 16, {
                duration: 1.5
            });
        }
    }, [selectedAlert, map]);

    return null;
};

// Theme-aware tile layer
const TILE_URLS = {
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
};

const ThemeAwareTileLayer = () => {
    const [isDark, setIsDark] = useState(
        document.documentElement.classList.contains('dark')
    );

    useEffect(() => {
        const observer = new MutationObserver(() => {
            setIsDark(document.documentElement.classList.contains('dark'));
        });
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['class'],
        });
        return () => observer.disconnect();
    }, []);

    return (
        <TileLayer
            key={isDark ? 'dark' : 'light'}
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            url={isDark ? TILE_URLS.dark : TILE_URLS.light}
        />
    );
};

export const IncidentMap = () => {
    const { alerts, activeAlerts, selectedAlert } = useDetection();
    const center = { lat: 0.0, lng: 0.0 };

    return (
        <Card className="h-full bg-card dark:bg-[#0A0A0A] border border-border dark:border-white/10 overflow-hidden relative shadow-lg flex flex-col">
            <CardHeader className="py-3 px-4 border-b border-border dark:border-white/5 bg-card/80 dark:bg-white/[0.02] absolute top-0 left-0 right-0 z-[1000] backdrop-blur-sm pointer-events-none">
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center text-xs font-mono uppercase tracking-widest text-foreground/80 dark:text-white/80">
                        <Navigation className="w-4 h-4 mr-2" />
                        Tactical Map
                    </CardTitle>
                    <Badge variant="outline" className="text-[10px] font-mono border-cyan-500/30 text-cyan-600 dark:text-cyan-400 bg-cyan-500/10">
                        {activeAlerts.length} TARGETS
                    </Badge>
                </div>
            </CardHeader>

            <CardContent className="flex-1 p-0 relative">
                <MapContainer
                    center={[center.lat, center.lng]}
                    zoom={13}
                    scrollWheelZoom={true}
                    className="h-full w-full z-0"
                    style={{ background: 'hsl(var(--background))' }}
                >
                    <ThemeAwareTileLayer />
                    <MapController />

                    {activeAlerts.map(alert => (
                        <Marker
                            key={alert.id}
                            position={[alert.lat, alert.lon]}
                        >
                            <Popup className="custom-popup">
                                <div className="text-xs font-mono">
                                    <strong className={alert.type === 'LIFE' ? 'text-red-600' : 'text-orange-500'}>
                                        {alert.type} DETECTED
                                    </strong>
                                    <br />
                                    Conf: {(alert.confidence * 100).toFixed(0)}%
                                    <br />
                                    Temp: {alert.max_temp.toFixed(1)}°C
                                </div>
                            </Popup>
                        </Marker>
                    ))}
                </MapContainer>

                {/* Overlay Grid */}
                <div className="absolute inset-0 pointer-events-none z-[400] opacity-10 dark:opacity-20 bg-[linear-gradient(rgba(0,0,0,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.05)_1px,transparent_1px)] dark:bg-[linear-gradient(rgba(0,255,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,255,0.05)_1px,transparent_1px)] bg-[size:20px_20px]" />

                {/* Corner Accents */}
                <div className="absolute bottom-4 right-4 pointer-events-none z-[400] border-b-2 border-r-2 border-foreground/30 dark:border-cyan-500/50 w-8 h-8" />
                <div className="absolute bottom-4 left-4 pointer-events-none z-[400] border-b-2 border-l-2 border-foreground/30 dark:border-cyan-500/50 w-8 h-8" />

            </CardContent>
        </Card>
    );
};
