import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useIsMobile } from '@/hooks/use-mobile';
import {
  Navigation,
  MapPin,
  Satellite,
  Clock,
  Copy,
  ExternalLink,
  MoreVertical
} from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';

interface GPSData {
  latitude: number;
  longitude: number;
  altitude: number;
  accuracy: number;
  timestamp: Date;
  speed?: number;
  heading?: number;
}

export const GPSCoordinateBox = () => {
  const [isMapOpen, setIsMapOpen] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const isMobile = useIsMobile();

  // Fetch GPS Data
  const { data: gpsData = null } = useQuery<GPSData>({
    queryKey: ['gps'],
    queryFn: async () => {
      const res = await apiFetch('/api/gps');
      if (!res.ok) throw new Error('Failed to fetch GPS');
      const data = await res.json();
      return {
        ...data,
        timestamp: new Date(data.timestamp)
      };
    },
    refetchInterval: 1000, // Poll every 1s for GPS
  });

  useEffect(() => {
    if (gpsData) {
      setLastUpdate(new Date());
    }
  }, [gpsData]);

  const formatCoordinate = (coord: number, type: 'lat' | 'lng') => {
    const direction = type === 'lat' ? (coord >= 0 ? 'N' : 'S') : (coord >= 0 ? 'E' : 'W');
    const absCoord = Math.abs(coord);
    const degrees = Math.floor(absCoord);
    const minutes = ((absCoord - degrees) * 60);
    return `${degrees}°${minutes.toFixed(2)}'${direction}`;
  };

  const copyCoordinates = () => {
    if (gpsData) {
      const coordText = `${gpsData.latitude.toFixed(6)}, ${gpsData.longitude.toFixed(6)}`;
      navigator.clipboard.writeText(coordText);
      toast({
        title: "Copied to clipboard",
        description: "GPS coordinates copied successfully",
      });
    }
  };

  const openInMaps = () => {
    if (gpsData) {
      const url = `https://www.google.com/maps?q=${gpsData.latitude},${gpsData.longitude}`;
      window.open(url, '_blank');
    }
  };

  const getTimeSinceUpdate = () => {
    if (!lastUpdate) return 'No data';
    const now = new Date();
    const diff = (now.getTime() - lastUpdate.getTime()) / 1000;

    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <>
      <Card className="bg-card/40 backdrop-blur-md border-border dark:border-white/10 overflow-hidden relative group">

        {/* Decorative Background Elements */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(34,211,238,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.03)_1px,transparent_1px)] bg-[size:20px_20px] pointer-events-none" />
        <div className="absolute top-0 right-0 p-2 opacity-50">
          <div className="w-16 h-16 border-t-2 border-r-2 border-cyan-500/20 rounded-tr-3xl" />
        </div>
        <div className="absolute bottom-0 left-0 p-2 opacity-50">
          <div className="w-16 h-16 border-b-2 border-l-2 border-cyan-500/20 rounded-bl-3xl" />
        </div>

        <CardHeader className="pb-2 relative z-10 flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm font-bold uppercase tracking-widest text-muted-foreground flex items-center">
            <Navigation className="w-4 h-4 mr-2 text-cyan-500" />
            GLOBAL POSITIONING
          </CardTitle>
          <div className={`flex items-center space-x-2 px-2 py-1 rounded-full border ${gpsData ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500' : 'bg-yellow-500/10 border-yellow-500/20 text-yellow-500'}`}>
            <div className={`w-2 h-2 rounded-full ${gpsData ? 'bg-emerald-500 animate-pulse' : 'bg-yellow-500 animate-bounce'}`} />
            <span className="text-[10px] font-mono font-bold">{gpsData ? 'LOCKED' : 'SEARCHING'}</span>
          </div>
        </CardHeader>

        <CardContent className="space-y-6 relative z-10">
          {gpsData ? (
            <>
              {/* Main Digital Coordinates */}
              <div className="space-y-4">
                <div className="flex items-baseline justify-between border-b border-border/50 pb-2">
                  <span className="text-xs text-muted-foreground font-mono">LAT</span>
                  <div className="text-3xl sm:text-4xl font-black font-mono tracking-tighter text-foreground tabular-nums">
                    {gpsData.latitude.toFixed(6)}<span className="text-base text-muted-foreground ml-1">°N</span>
                  </div>
                </div>
                <div className="flex items-baseline justify-between border-b border-border/50 pb-2">
                  <span className="text-xs text-muted-foreground font-mono">LON</span>
                  <div className="text-3xl sm:text-4xl font-black font-mono tracking-tighter text-foreground tabular-nums">
                    {gpsData.longitude.toFixed(6)}<span className="text-base text-muted-foreground ml-1">°E</span>
                  </div>
                </div>
              </div>

              {/* Data Strip */}
              <div className="grid grid-cols-3 gap-2 py-2 bg-black/20 rounded-lg border border-white/5">
                <div className="flex flex-col items-center">
                  <span className="text-[10px] text-muted-foreground uppercase">ALT</span>
                  <span className="text-sm font-mono font-bold text-cyan-400">{gpsData.altitude.toFixed(1)}m</span>
                </div>
                <div className="flex flex-col items-center border-l border-white/5">
                  <span className="text-[10px] text-muted-foreground uppercase">SPD</span>
                  <span className="text-sm font-mono font-bold text-cyan-400">{gpsData.speed?.toFixed(1) || 0}km/h</span>
                </div>
                <div className="flex flex-col items-center border-l border-white/5">
                  <span className="text-[10px] text-muted-foreground uppercase">HDG</span>
                  <span className="text-sm font-mono font-bold text-cyan-400">{gpsData.heading?.toFixed(0) || 0}°</span>
                </div>
              </div>

              {/* Actions */}
              <div className="grid grid-cols-2 gap-3 pt-2">
                <Button variant="outline" size="sm" onClick={copyCoordinates} className="border-dashed border-cyan-500/30 hover:bg-cyan-500/10 hover:text-cyan-400">
                  <Copy className="w-3 h-3 mr-2" />
                  <span className="text-xs font-mono">COPY DATA</span>
                </Button>
                <Button size="sm" onClick={() => setIsMapOpen(true)} className="bg-cyan-500 hover:bg-cyan-600 text-black font-bold">
                  <MapPin className="w-3 h-3 mr-2" />
                  <span className="text-xs font-mono">TACTICAL MAP</span>
                </Button>
              </div>

              <div className="text-[10px] text-center text-muted-foreground font-mono opacity-50">
                LAST UPDATE: {getTimeSinceUpdate()}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-10 space-y-4">
              <div className="relative">
                <div className="absolute inset-0 bg-cyan-500/20 blur-xl rounded-full animate-pulse" />
                <Satellite className="w-12 h-12 text-cyan-500/50 animate-bounce relative z-10" />
              </div>
              <div className="text-center space-y-1">
                <div className="text-sm font-bold text-cyan-500 font-mono tracking-wider">ACQUIRING SATELLITE LOCK</div>
                <div className="text-xs text-muted-foreground">Triangulating position...</div>
              </div>

              {/* Mock loading bars */}
              <div className="w-full max-w-[200px] space-y-1 opacity-50">
                <div className="h-1 bg-cyan-900/50 rounded-full overflow-hidden">
                  <div className="h-full bg-cyan-500 animate-[loading_2s_ease-in-out_infinite]" style={{ width: '60%' }} />
                </div>
                <div className="h-1 bg-cyan-900/50 rounded-full overflow-hidden">
                  <div className="h-full bg-cyan-500 animate-[loading_3s_ease-in-out_infinite] delay-75" style={{ width: '40%' }} />
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isMapOpen} onOpenChange={setIsMapOpen}>
        <DialogContent className="border-cyan-500/20 bg-black/90 backdrop-blur-xl">
          <DialogHeader>
            <DialogTitle className="flex items-center text-cyan-500 font-mono uppercase tracking-widest">
              <MapPin className="w-4 h-4 mr-2" />
              Tactical Map View
            </DialogTitle>
          </DialogHeader>
          <div className="aspect-video bg-cyan-950/20 rounded-lg flex items-center justify-center border border-cyan-500/30 relative overflow-hidden group">
            {/* Grid bg for map placeholder */}
            <div className="absolute inset-0 bg-[linear-gradient(rgba(34,211,238,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.1)_1px,transparent_1px)] bg-[size:40px_40px]" />

            {gpsData && (
              <div className="text-center z-10 space-y-4">
                <div className="inline-block p-4 rounded-full bg-cyan-500/10 border border-cyan-500/50 shadow-[0_0_30px_rgba(34,211,238,0.2)]">
                  <MapPin className="w-8 h-8 text-cyan-400" />
                </div>
                <div>
                  <div className="text-2xl font-bold font-mono text-white tracking-widest">TARGET LOCATED</div>
                  <div className="text-cyan-400 font-mono">
                    {gpsData.latitude.toFixed(6)}, {gpsData.longitude.toFixed(6)}
                  </div>
                </div>
                <Button
                  className="bg-cyan-500 text-black hover:bg-cyan-400 font-bold"
                  onClick={openInMaps}
                >
                  <ExternalLink className="w-3 h-3 mr-2" />
                  OPEN GOOGLE MAPS
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};