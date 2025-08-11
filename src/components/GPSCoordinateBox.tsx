import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { 
  Navigation, 
  MapPin, 
  Satellite,
  Clock,
  Copy,
  ExternalLink
} from 'lucide-react';
import { toast } from '@/hooks/use-toast';

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
  const [gpsData, setGpsData] = useState<GPSData | null>(null);
  const [isMapOpen, setIsMapOpen] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // Simulate GPS data updates
  useEffect(() => {
    const simulateGPSData = () => {
      // Base location (you can change this to any coordinates)
      const baseLat = 40.7128 + (Math.random() - 0.5) * 0.01; // New York area
      const baseLng = -74.0060 + (Math.random() - 0.5) * 0.01;
      
      const newGpsData: GPSData = {
        latitude: baseLat,
        longitude: baseLng,
        altitude: 50 + Math.random() * 20,
        accuracy: 3 + Math.random() * 2,
        timestamp: new Date(),
        speed: Math.random() * 10,
        heading: Math.random() * 360
      };

      setGpsData(newGpsData);
      setLastUpdate(new Date());
    };

    // Initial data
    simulateGPSData();

    // Update every 5 seconds
    const interval = setInterval(simulateGPSData, 5000);
    return () => clearInterval(interval);
  }, []);

  const formatCoordinate = (coord: number, type: 'lat' | 'lng') => {
    const direction = type === 'lat' ? (coord >= 0 ? 'N' : 'S') : (coord >= 0 ? 'E' : 'W');
    const absCoord = Math.abs(coord);
    const degrees = Math.floor(absCoord);
    const minutes = ((absCoord - degrees) * 60);
    return `${degrees}°${minutes.toFixed(4)}'${direction}`;
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
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center text-lg">
              <Navigation className="w-5 h-5 mr-2" />
              GPS Coordinates
            </CardTitle>
            <Badge 
              variant="outline" 
              className={`
                ${gpsData 
                  ? 'bg-success/20 text-success border-success/30' 
                  : 'bg-muted/20 text-muted-foreground border-muted/30'
                }
              `}
            >
              <Satellite className="w-3 h-3 mr-1" />
              {gpsData ? 'GPS Lock' : 'Searching'}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {gpsData ? (
            <>
              {/* Coordinate Display */}
              <div className="space-y-3">
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

                {/* Last Update */}
                <div className="flex items-center justify-center text-xs text-muted-foreground">
                  <Clock className="w-3 h-3 mr-1" />
                  Last update: {getTimeSinceUpdate()}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex space-x-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={copyCoordinates}
                  className="flex-1"
                >
                  <Copy className="w-4 h-4 mr-1" />
                  Copy
                </Button>
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
              </div>
            </>
          ) : (
            <div className="text-center py-6">
              <Satellite className="w-8 h-8 mx-auto text-muted-foreground mb-2 animate-pulse" />
              <p className="text-sm text-muted-foreground">Acquiring GPS signal...</p>
              <p className="text-xs text-muted-foreground mt-1">Please wait while we connect to satellites</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Map Dialog */}
      <Dialog open={isMapOpen} onOpenChange={setIsMapOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center">
              <MapPin className="w-5 h-5 mr-2" />
              Current Location
            </DialogTitle>
          </DialogHeader>
          <div className="aspect-video bg-muted/20 rounded-lg flex items-center justify-center border border-dashboard-panel-border">
            {gpsData && (
              <div className="text-center">
                <MapPin className="w-12 h-12 mx-auto text-primary mb-4" />
                <h3 className="text-lg font-semibold mb-2">Interactive Map</h3>
                <p className="text-sm text-muted-foreground mb-2">
                  Coordinates: {gpsData.latitude.toFixed(6)}, {gpsData.longitude.toFixed(6)}
                </p>
                <p className="text-xs text-muted-foreground">
                  Map integration would be displayed here
                </p>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="mt-4"
                  onClick={openInMaps}
                >
                  <ExternalLink className="w-4 h-4 mr-1" />
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