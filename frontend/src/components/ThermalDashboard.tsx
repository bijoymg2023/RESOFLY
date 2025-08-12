import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { VideoStreamBox } from './VideoStreamBox';
import { ThermalHeatMap } from './ThermalHeatMap';
import { AlertBox } from './AlertBox';
import { GPSCoordinateBox } from './GPSCoordinateBox';
import { ThemeToggle } from './ThemeToggle';
import { useIsMobile } from '@/hooks/use-mobile';
import { 
  Activity,
  Thermometer,
  AlertTriangle,
  Navigation,
  Monitor,
  Menu,
  X
} from 'lucide-react';

const ThermalDashboard = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isMobile = useIsMobile();

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile-Optimized Header */}
      <header className="flex items-center justify-between p-4 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex items-center space-x-2 sm:space-x-3">
          <div className="p-1.5 sm:p-2 rounded-lg bg-gradient-primary shadow-glow">
            <Thermometer className="h-4 w-4 sm:h-6 sm:w-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg sm:text-2xl font-bold text-foreground">
              ResoFly
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground hidden sm:block">
              Real-time monitoring and surveillance
            </p>
          </div>
        </div>
        
        <div className="flex items-center space-x-2 sm:space-x-4">
          <Badge variant="outline" className="bg-success/20 text-success border-success/30 text-xs sm:text-sm">
            <Activity className="w-2 h-2 sm:w-3 sm:h-3 mr-1" />
            {isMobile ? 'Active' : 'System Active'}
          </Badge>
          <ThemeToggle />
          
          {/* Mobile menu button */}
          {isMobile && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="sm:hidden"
            >
              {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </Button>
          )}
        </div>
      </header>

      {/* Mobile Navigation Overlay */}
      {isMobile && mobileMenuOpen && (
        <div className="fixed inset-0 top-16 bg-background/95 backdrop-blur-sm z-40 sm:hidden">
          <div className="p-4 space-y-3">
            <Button variant="outline" className="w-full justify-start" onClick={() => setMobileMenuOpen(false)}>
              <Monitor className="w-4 h-4 mr-2" />
              System Overview
            </Button>
            <Button variant="outline" className="w-full justify-start" onClick={() => setMobileMenuOpen(false)}>
              <AlertTriangle className="w-4 h-4 mr-2" />
              View Alerts
            </Button>
            <Button variant="outline" className="w-full justify-start" onClick={() => setMobileMenuOpen(false)}>
              <Navigation className="w-4 h-4 mr-2" />
              GPS Location
            </Button>
          </div>
        </div>
      )}

      {/* Main Dashboard Content */}
      <div className="p-2 sm:p-4 lg:p-6 space-y-4 sm:space-y-6">
        {/* Mobile-First Responsive Layout */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 sm:gap-6">
          
          {/* Primary Content Area - Video Stream */}
          <div className="xl:col-span-8 space-y-4 sm:space-y-6">
            {/* Video Stream */}
            <div className="min-h-[250px] sm:min-h-[400px]">
              <VideoStreamBox />
            </div>
            
            {/* Bottom Row - Heat Map and Alerts (Mobile: Stack vertically) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
              <div className="min-h-[300px] sm:min-h-[320px]">
                <ThermalHeatMap />
              </div>
              <div className="min-h-[300px] sm:min-h-[320px]">
                <AlertBox />
              </div>
            </div>
          </div>

          {/* Secondary Content Area - GPS and System Status */}
          <div className="xl:col-span-4 space-y-4 sm:space-y-6">
            
            {/* GPS Coordinates */}
            <GPSCoordinateBox />
            
            {/* System Status Card */}
            <Card className="bg-dashboard-panel border-dashboard-panel-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm sm:text-base font-medium flex items-center">
                  <Monitor className="w-4 h-4 mr-2" />
                  System Status
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-1 gap-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Temperature Sensors</span>
                    <Badge variant="outline" className="bg-success/20 text-success border-success/30 text-xs">
                      Online
                    </Badge>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">RGB Camera</span>
                    <Badge variant="outline" className="bg-success/20 text-success border-success/30 text-xs">
                      Active
                    </Badge>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">GPS Module</span>
                    <Badge variant="outline" className="bg-success/20 text-success border-success/30 text-xs">
                      Connected
                    </Badge>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Data Link</span>
                    <Badge variant="outline" className="bg-warning/20 text-warning border-warning/30 text-xs">
                      <Activity className="w-2 h-2 sm:w-3 sm:h-3 mr-1 animate-pulse" />
                      Transmitting
                    </Badge>
                  </div>
                </div>

                {/* Mobile: Additional system info */}
                {isMobile && (
                  <div className="mt-4 pt-3 border-t border-border">
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="text-center p-2 bg-muted/20 rounded">
                        <div className="text-primary font-bold">98%</div>
                        <div className="text-muted-foreground">Uptime</div>
                      </div>
                      <div className="text-center p-2 bg-muted/20 rounded">
                        <div className="text-success font-bold">42°C</div>
                        <div className="text-muted-foreground">Max Temp</div>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Mobile: Quick Actions */}
            {isMobile && (
              <Card className="bg-dashboard-panel border-dashboard-panel-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Quick Actions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-2">
                    <Button variant="outline" size="sm" className="h-12 flex-col">
                      <AlertTriangle className="w-4 h-4 mb-1" />
                      <span className="text-xs">Alerts</span>
                    </Button>
                    <Button variant="outline" size="sm" className="h-12 flex-col">
                      <Navigation className="w-4 h-4 mb-1" />
                      <span className="text-xs">GPS</span>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThermalDashboard;