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
      <Card className="bg-dashboard-panel border-dashboard-panel-border">
        <CardHeader className="pb-3 sm:pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center text-base sm:text-lg">
              <Navigation className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
              {isMobile ? 'GPS' : 'GPS Coordinates'}
            </CardTitle>
            <div className="flex items-center space-x-2">
              <Badge
                variant="outline"
                className={`text-xs sm:text-sm
                  ${gpsData
                    ? 'bg-success/20 text-success border-success/30'
                    : 'bg-muted/20 text-muted-foreground border-muted/30'
                  }
                `}
              >
                <Satellite className="w-2 h-2 sm:w-3 sm:h-3 mr-1" />
                {gpsData ? (isMobile ? 'Lock' : 'GPS Lock') : 'Searching'}
              </Badge>
              {isMobile && gpsData && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDetails(!showDetails)}
                  className="h-6 w-6 p-0"
                >
                  <MoreVertical className="w-3 h-3" />
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-3 sm:space-y-4">
          {gpsData ? (
            <>
              {/* Mobile-Optimized Coordinate Display */}
              <div className="space-y-3">
                {isMobile ? (
                  // Mobile: Compact vertical layout
                  <div className="space-y-2">
                    <div className="flex justify-between items-center p-2 bg-muted/20 rounded-lg border border-dashboard-panel-border">
                      <div>
                        <p className="text-xs text-muted-foreground">Latitude</p>
                        <p className="text-sm font-mono">{gpsData.latitude.toFixed(4)}°</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-muted-foreground">Longitude</p>
                        <p className="text-sm font-mono">{gpsData.longitude.toFixed(4)}°</p>
                      </div>
                    </div>

                    {/* Expandable details on mobile */}
                    {showDetails && (
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Alt:</span>
                          <span className="font-mono">{gpsData.altitude.toFixed(1)}m</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Acc:</span>
                          <span className="font-mono">±{gpsData.accuracy.toFixed(1)}m</span>
                        </div>
                        {gpsData.speed !== undefined && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Speed:</span>
                            <span className="font-mono">{gpsData.speed.toFixed(1)} km/h</span>
                          </div>
                        )}
                        {gpsData.heading !== undefined && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Head:</span>
                            <span className="font-mono">{gpsData.heading.toFixed(0)}°</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  // Desktop: Original grid layout
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="text-center p-3 bg-muted/20 rounded-lg border border-dashboard-panel-border">
                        <p className="text-xs text-muted-foreground mb-1">Latitude</p>
                        <p className="text-sm font-mono">{gpsData.latitude.toFixed(6)}°</p>
                        <p className="text-xs text-muted-foreground">{formatCoordinate(gpsData.latitude, 'lat')}</p>
                      </div>
                      <div className="text-center p-3 bg-muted/20 rounded-lg border border-dashboard-panel-border">
                        <p className="text-xs text-muted-foreground mb-1">Longitude</p>
                        <p className="text-sm font-mono">{gpsData.longitude.toFixed(6)}°</p>
                        <p className="text-xs text-muted-foreground">{formatCoordinate(gpsData.longitude, 'lng')}</p>
                      </div>
                    </div>

                    {/* Additional GPS Info */}
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Altitude:</span>
                        <span className="font-mono">{gpsData.altitude.toFixed(1)}m</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Accuracy:</span>
                        <span className="font-mono">±{gpsData.accuracy.toFixed(1)}m</span>
                      </div>
                      {gpsData.speed !== undefined && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Speed:</span>
                          <span className="font-mono">{gpsData.speed.toFixed(1)} km/h</span>
                        </div>
                      )}
                      {gpsData.heading !== undefined && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Heading:</span>
                          <span className="font-mono">{gpsData.heading.toFixed(0)}°</span>
                        </div>
                      )}
                    </div>
                  </>
                )}

                {/* Last Update */}
                <div className="flex items-center justify-center text-xs text-muted-foreground">
                  <Clock className="w-2 h-2 sm:w-3 sm:h-3 mr-1" />
                  Last update: {getTimeSinceUpdate()}
                </div>
              </div>

              {/* Mobile-Optimized Action Buttons */}
              <div className={`flex ${isMobile ? 'flex-col space-y-2' : 'space-x-2'}`}>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyCoordinates}
                  className={isMobile ? 'w-full' : 'flex-1'}
                >
                  <Copy className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
                  {isMobile ? 'Copy Coordinates' : 'Copy'}
                </Button>

                {isMobile ? (
                  <div className="flex space-x-2">
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => setIsMapOpen(true)}
                      className="flex-1"
                    >
                      <MapPin className="w-3 h-3 mr-1" />
                      View Map
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={openInMaps}
                      className="flex-1"
                    >
                      <ExternalLink className="w-3 h-3 mr-1" />
                      Open
                    </Button>
                  </div>
                ) : (
                  <>
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => setIsMapOpen(true)}
                      className="flex-1"
                    >
                      <MapPin className="w-4 h-4 mr-1" />
                      View Map
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={openInMaps}
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Button>
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="text-center py-4 sm:py-6">
              <Satellite className="w-6 h-6 sm:w-8 sm:h-8 mx-auto text-muted-foreground mb-2 animate-pulse" />
              <p className="text-sm text-muted-foreground">Acquiring GPS signal...</p>
              <p className="text-xs text-muted-foreground mt-1">
                {isMobile ? 'Connecting to satellites' : 'Please wait while we connect to satellites'}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Map Dialog - Mobile Responsive */}
      <Dialog open={isMapOpen} onOpenChange={setIsMapOpen}>
        <DialogContent className={`${isMobile ? 'max-w-[90vw]' : 'max-w-2xl'}`}>
          <DialogHeader>
            <DialogTitle className="flex items-center text-base sm:text-lg">
              <MapPin className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
              Current Location
            </DialogTitle>
          </DialogHeader>
          <div className="aspect-video bg-muted/20 rounded-lg flex items-center justify-center border border-dashboard-panel-border">
            {gpsData && (
              <div className="text-center p-4">
                <MapPin className="w-8 h-8 sm:w-12 sm:h-12 mx-auto text-primary mb-4" />
                <h3 className="text-base sm:text-lg font-semibold mb-2">Interactive Map</h3>
                <p className="text-xs sm:text-sm text-muted-foreground mb-2">
                  Coordinates: {gpsData.latitude.toFixed(6)}, {gpsData.longitude.toFixed(6)}
                </p>
                <p className="text-xs text-muted-foreground mb-4">
                  Map integration would be displayed here
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openInMaps}
                  className="w-full sm:w-auto"
                >
                  <ExternalLink className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
                  Open in Google Maps
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};