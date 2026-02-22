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
  Copy,
  ExternalLink,
  Map as MapIcon
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
  speed: number;
  climb: number;
  heading?: number;
  source?: 'hardware' | 'network' | 'none';
}

export const GPSCoordinateBox = () => {
  const [isMapOpen, setIsMapOpen] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
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

  const getSourceDisplay = () => {
    if (!gpsData || !gpsData.source || gpsData.source === 'none') return 'SEARCHING';
    return gpsData.source === 'hardware' ? 'HARDWARE' : 'NETWORK';
  };

  const getSourceIcon = () => {
    if (gpsData?.source === 'network') return <Navigation className="w-4 h-4 text-cyan-500" />;
    return <Satellite className="w-4 h-4 text-emerald-500" />;
  };

  return (
    <>
      <Card className="h-full bg-card/40 backdrop-blur-sm border-border dark:border-white/10 overflow-hidden flex flex-col shadow-lg">
        {/* Header - Matching Signal Tracker Style */}
        <CardHeader className="py-3 px-4 flex flex-row items-center justify-between space-y-0 border-b border-white/10 bg-black/60">
          <div className="flex items-center space-x-2">
            {getSourceIcon()}
            <CardTitle className="text-[10px] font-black uppercase tracking-[0.3em] text-white/60">POSITION_LOCK</CardTitle>
          </div>
          <Badge
            variant="outline"
            className={`text-[9px] h-5 px-2 border-white/10 font-bold tracking-widest ${gpsData && gpsData.source !== 'none' ? 'text-emerald-500 border-emerald-500/20 bg-emerald-500/10' : 'text-muted-foreground'
              }`}
          >
            {getSourceDisplay()}
          </Badge>
        </CardHeader>

        <CardContent className="p-0 flex-1 flex flex-col relative">
          {/* Main Coordinates Display */}
          <div className="flex-1 flex flex-col justify-center items-center bg-black/80 border-b border-white/10 relative overflow-hidden p-4">
            {/* Grid Overlay */}
            <div className="absolute inset-0 bg-[linear-gradient(rgba(0,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,255,0.03)_1px,transparent_1px)] bg-[size:20px_20px]" />

            {gpsData ? (
              <div className="z-10 w-full space-y-4">
                <div className="flex justify-between items-baseline border-b border-white/10 pb-2">
                  <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">LAT</span>
                  <div className="text-3xl sm:text-4xl font-black font-mono tracking-tighter text-white tabular-nums">
                    {gpsData.latitude.toFixed(6)}<span className="text-sm text-cyan-500 ml-1">°N</span>
                  </div>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">LON</span>
                  <div className="text-3xl sm:text-4xl font-black font-mono tracking-tighter text-white tabular-nums">
                    {gpsData.longitude.toFixed(6)}<span className="text-sm text-cyan-500 ml-1">°E</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="z-10 text-center space-y-2 opacity-50">
                <Satellite className="w-12 h-12 mx-auto text-muted-foreground animate-pulse" />
                <div className="text-[10px] font-mono uppercase tracking-widest">Acquiring Satellite Lock...</div>
              </div>
            )}
          </div>

          {/* Secondary Data Strip */}
          <div className="bg-black/90 p-3 grid grid-cols-3 gap-2 border-t border-white/5">
            <div className="text-center p-2 rounded bg-white/5 border border-white/5">
              <div className="text-[9px] text-muted-foreground font-mono uppercase mb-1">ALTITUDE</div>
              <div className="font-bold font-mono text-emerald-400">{gpsData ? `${gpsData.altitude.toFixed(1)}m` : '--'}</div>
            </div>
            <div className="text-center p-2 rounded bg-white/5 border border-white/5">
              <div className="text-[9px] text-muted-foreground font-mono uppercase mb-1">SPEED</div>
              <div className="font-bold font-mono text-cyan-400">{gpsData ? `${gpsData.speed?.toFixed(1) || 0}km/h` : '--'}</div>
            </div>
            <div className="text-center p-2 rounded bg-white/5 border border-white/5">
              <div className="text-[9px] text-muted-foreground font-mono uppercase mb-1">HEADING</div>
              <div className="font-bold font-mono text-purple-400">{gpsData ? `${(gpsData.heading || gpsData.climb || 0).toFixed(0)}°` : '--'}</div>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="p-2 bg-card/20 flex gap-2">
            <Button
              variant="outline"
              className="flex-1 h-8 text-[10px] border-white/10 hover:bg-white/5 font-mono uppercase"
              onClick={copyCoordinates}
              disabled={!gpsData}
            >
              <Copy className="w-3 h-3 mr-2" />
              Copy Data
            </Button>
            <Button
              className="flex-1 h-8 text-[10px] bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 border border-cyan-500/50 font-mono uppercase"
              onClick={() => setIsMapOpen(true)}
            >
              <MapIcon className="w-3 h-3 mr-2" />
              Tactical Map
            </Button>
          </div>

          <div className="text-[10px] text-center text-muted-foreground font-mono opacity-50 pb-1">
            LAST UPDATE: {getTimeSinceUpdate()}
          </div>
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
            {gpsData ? (
              <iframe
                width="100%"
                height="100%"
                frameBorder="0"
                style={{ border: 0 }}
                src={`https://maps.google.com/maps?q=${gpsData.latitude},${gpsData.longitude}&z=16&output=embed`}
                title="Tactical GPS Map"
                className="absolute inset-0 z-10"
              />
            ) : (
              <>
                <div className="absolute inset-0 bg-[linear-gradient(rgba(34,211,238,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.1)_1px,transparent_1px)] bg-[size:40px_40px]" />
                <div className="text-center z-10 space-y-4">
                  <div className="inline-block p-4 rounded-full bg-cyan-500/10 border border-cyan-500/50 shadow-[0_0_30px_rgba(34,211,238,0.2)]">
                    <MapPin className="w-8 h-8 text-cyan-400" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold font-mono text-white tracking-widest">ACQUIRING SIGNAL</div>
                  </div>
                </div>
              </>
            )}

            {/* Overlay for coordinates & external link button */}
            {gpsData && (
              <div className="absolute bottom-4 left-4 right-4 z-20 flex justify-between items-end pointer-events-none">
                <div className="bg-black/80 backdrop-blur-md border border-cyan-500/30 p-2 rounded pointer-events-auto">
                  <div className="text-[10px] font-bold font-mono text-white tracking-widest">TARGET LOCATED</div>
                  <div className="text-cyan-400 font-mono text-sm">
                    {gpsData.latitude.toFixed(6)}, {gpsData.longitude.toFixed(6)}
                  </div>
                </div>

                <Button
                  className="bg-cyan-500/90 text-black hover:bg-cyan-400 font-bold pointer-events-auto backdrop-blur"
                  onClick={openInMaps}
                >
                  <ExternalLink className="w-3 h-3 mr-2" />
                  OPEN FULL MAP
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};