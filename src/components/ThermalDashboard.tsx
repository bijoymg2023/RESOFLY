import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { VideoStreamBox } from './VideoStreamBox';
import { ThermalHeatMap } from './ThermalHeatMap';
import { AlertBox } from './AlertBox';
import { GPSCoordinateBox } from './GPSCoordinateBox';
import { ThemeToggle } from './ThemeToggle';
import { 
  Activity,
  Thermometer,
  AlertTriangle,
  Navigation,
  Monitor
} from 'lucide-react';

const ThermalDashboard = () => {
  return (
    <div className="min-h-screen bg-background p-4">
      {/* Header */}
      <header className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-gradient-primary shadow-glow">
            <Thermometer className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Thermal Vision Hub</h1>
            <p className="text-muted-foreground">Real-time monitoring and surveillance</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-4">
          <Badge variant="outline" className="bg-success/20 text-success border-success/30">
            <Activity className="w-3 h-3 mr-1" />
            System Active
          </Badge>
          <ThemeToggle />
        </div>
      </header>

      {/* Main Dashboard Grid */}
      <div className="grid grid-cols-12 gap-4 h-[calc(100vh-140px)]">
        {/* Left Column - Video Stream (Takes most space) */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          <VideoStreamBox />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-1/2">
            <ThermalHeatMap />
            <div className="space-y-4">
              <AlertBox />
            </div>
          </div>
        </div>

        {/* Right Column - GPS and Controls */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <GPSCoordinateBox />
          
          {/* System Status Card */}
          <Card className="bg-dashboard-panel border-dashboard-panel-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center">
                <Monitor className="w-4 h-4 mr-2" />
                System Status
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Temperature Sensors</span>
                <Badge variant="outline" className="bg-success/20 text-success border-success/30">
                  Online
                </Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">RGB Camera</span>
                <Badge variant="outline" className="bg-success/20 text-success border-success/30">
                  Active
                </Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">GPS Module</span>
                <Badge variant="outline" className="bg-success/20 text-success border-success/30">
                  Connected
                </Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Data Link</span>
                <Badge variant="outline" className="bg-warning/20 text-warning border-warning/30">
                  <Activity className="w-3 h-3 mr-1 animate-pulse" />
                  Transmitting
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ThermalDashboard;