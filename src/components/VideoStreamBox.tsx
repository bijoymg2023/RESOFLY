import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useIsMobile } from '@/hooks/use-mobile';
import {
  Video,
  Thermometer,
  Layers,
  Play,
  Pause,
  Maximize,
  Settings,
  MoreHorizontal
} from 'lucide-react';

type VideoType = 'RGB' | 'Thermal' | 'Overlay';

export const VideoStreamBox = () => {
  const [activeType, setActiveType] = useState<VideoType>('RGB');
  const [isPlaying, setIsPlaying] = useState(true);
  const [showAllControls, setShowAllControls] = useState(false);
  const isMobile = useIsMobile();

  const videoTypes = [
    { key: 'RGB' as VideoType, label: 'RGB', icon: Video, color: 'primary' },
    { key: 'Thermal' as VideoType, label: 'Thermal', icon: Thermometer, color: 'thermal' },
    { key: 'Overlay' as VideoType, label: 'Overlay', icon: Layers, color: 'accent' }
  ];

  const getStreamBackground = () => {
    switch (activeType) {
      case 'RGB':
        return 'bg-gradient-to-br from-primary/20 to-accent/20';
      case 'Thermal':
        return 'bg-gradient-thermal opacity-20';
      case 'Overlay':
        return 'bg-gradient-to-br from-accent/20 to-primary/20';
    }
  };

  return (
    <Card className="h-full bg-dashboard-panel border-dashboard-panel-border">
      <CardHeader className="pb-3 sm:pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center text-base sm:text-lg">
            <Video className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
            {isMobile ? 'Live Stream' : 'Live Video Stream'}
          </CardTitle>
          <div className="flex items-center space-x-2">
            <Badge
              variant="outline"
              className={`text-xs sm:text-sm
                ${isPlaying
                  ? 'bg-success/20 text-success border-success/30'
                  : 'bg-muted/20 text-muted-foreground border-muted/30'
                }
              `}
            >
              {isPlaying ? (
                <>
                  <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-success rounded-full mr-1 animate-pulse" />
                  LIVE
                </>
              ) : (
                'PAUSED'
              )}
            </Badge>
          </div>
        </div>

        {/* Mobile-Responsive Stream Type Selector */}
        <div className="flex space-x-1 sm:space-x-2">
          {videoTypes.map(({ key, label, icon: Icon, color }) => (
            <Button
              key={key}
              variant={activeType === key ? "default" : "outline"}
              size={isMobile ? "sm" : "sm"}
              onClick={() => setActiveType(key)}
              className={`flex-1 sm:flex-none text-xs sm:text-sm justify-center items-center ${activeType === key
                ? `bg-${color} hover:bg-${color}/90`
                : 'hover:bg-muted/50'
                }`}
            >
              <Icon className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
              {isMobile ? label.charAt(0) : label}
            </Button>
          ))}
        </div>
      </CardHeader>

      <CardContent className="flex-1 p-0">
        {/* Video Display Area */}
        <div className="relative h-full min-h-[200px] sm:min-h-[300px] mx-2 sm:mx-4 mb-2 sm:mb-4 rounded-lg overflow-hidden bg-muted/20 border border-dashboard-panel-border">
          <div className={`absolute inset-0 ${getStreamBackground()}`} />

          {/* Live Video Content */}
          <div className="relative h-full flex items-center justify-center">
            {activeType === 'Thermal' ? (
              <img
                src="/api/stream/thermal"
                alt="Thermal Stream"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="text-center">
                <div className="mb-2 sm:mb-4">
                  {videoTypes.find(v => v.key === activeType)?.icon && (
                    React.createElement(
                      videoTypes.find(v => v.key === activeType)!.icon,
                      { className: "w-12 h-12 sm:w-16 sm:h-16 mx-auto text-muted-foreground/50" }
                    )
                  )}
                </div>
                <p className="text-base sm:text-lg font-medium text-muted-foreground">
                  {activeType} Stream
                </p>
                <p className="text-xs sm:text-sm text-muted-foreground/70">
                  {isPlaying ? 'Stream Active' : 'Stream Paused'}
                </p>
              </div>
            )}
          </div>

          {/* Stream Info Overlay */}
          <div className="absolute top-2 sm:top-4 left-2 sm:left-4 space-y-1 sm:space-y-2">
            <Badge variant="outline" className="bg-background/80 backdrop-blur-sm text-xs">
              {isMobile ? '720p • 30fps' : '1920x1080 • 30fps'}
            </Badge>
            {activeType === 'Thermal' && (
              <Badge variant="outline" className="bg-thermal/20 text-thermal border-thermal/30 backdrop-blur-sm text-xs">
                <Thermometer className="w-2 h-2 sm:w-3 sm:h-3 mr-1" />
                18°C - 42°C
              </Badge>
            )}
          </div>

          {/* Mobile-Optimized Controls Overlay */}
          <div className="absolute bottom-2 sm:bottom-4 right-2 sm:right-4">
            {isMobile ? (
              <div className="flex items-center space-x-1">
                <Button
                  size="sm"
                  variant="outline"
                  className="bg-background/80 backdrop-blur-sm w-8 h-8 p-0"
                  onClick={() => setIsPlaying(!isPlaying)}
                >
                  {isPlaying ? (
                    <Pause className="w-3 h-3" />
                  ) : (
                    <Play className="w-3 h-3" />
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="bg-background/80 backdrop-blur-sm w-8 h-8 p-0"
                  onClick={() => setShowAllControls(!showAllControls)}
                >
                  <MoreHorizontal className="w-3 h-3" />
                </Button>
              </div>
            ) : (
              <div className="flex space-x-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="bg-background/80 backdrop-blur-sm"
                  onClick={() => setIsPlaying(!isPlaying)}
                >
                  {isPlaying ? (
                    <Pause className="w-4 h-4" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="bg-background/80 backdrop-blur-sm"
                >
                  <Maximize className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="bg-background/80 backdrop-blur-sm"
                >
                  <Settings className="w-4 h-4" />
                </Button>
              </div>
            )}
          </div>

          {/* Mobile: Expanded Controls */}
          {isMobile && showAllControls && (
            <div className="absolute bottom-12 right-2 bg-background/95 backdrop-blur-sm rounded-lg p-2 border border-border">
              <div className="flex flex-col space-y-1">
                <Button size="sm" variant="ghost" className="justify-start h-8 px-2">
                  <Maximize className="w-3 h-3 mr-2" />
                  <span className="text-xs">Fullscreen</span>
                </Button>
                <Button size="sm" variant="ghost" className="justify-start h-8 px-2">
                  <Settings className="w-3 h-3 mr-2" />
                  <span className="text-xs">Settings</span>
                </Button>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};