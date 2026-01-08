import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
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
  const { token } = useAuth();

  // Base URL for the stream
  const THERMAL_STREAM_URL = '/api/stream/thermal';
  const RGB_STREAM_URL = '/api/stream/rgb';

  const getStreamUrl = (type: VideoType) => {
    const base = type === 'RGB' ? RGB_STREAM_URL : THERMAL_STREAM_URL;
    return token ? `${base}?token=${token}` : base;
  };

  const videoTypes = [
    { key: 'RGB' as VideoType, label: 'OPTICAL', icon: Video },
    { key: 'Thermal' as VideoType, label: 'THERMAL', icon: Thermometer },
    { key: 'Overlay' as VideoType, label: 'FUSION', icon: Layers }
  ];

  return (
    <Card className="h-full bg-[#0A0A0A] border border-white/10 overflow-hidden relative group shadow-2xl">
      {/* Card Header (Stream Selector) */}
      <div className="absolute top-0 left-0 right-0 z-20 flex justify-between items-start p-4 bg-gradient-to-b from-black/80 to-transparent">
        {/* Stream Type Tabs */}
        <div className="flex space-x-1 bg-black/50 backdrop-blur-md p-1 rounded-lg border border-white/10">
          {videoTypes.map((type) => (
            <button
              key={type.key}
              onClick={() => setActiveType(type.key)}
              className={`
                        px-3 py-1.5 rounded-md text-[10px] font-bold tracking-wider flex items-center space-x-2 transition-all duration-300
                        ${activeType === type.key
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
                  : 'text-white/40 hover:text-white hover:bg-white/5 border border-transparent'}
                    `}
            >
              <type.icon className="w-3 h-3" />
              <span className="hidden sm:inline">{type.label}</span>
            </button>
          ))}
        </div>

        {/* Record/Live Status */}
        <div className="flex items-center space-x-2">
          <div className={`flex items-center space-x-2 px-3 py-1.5 rounded-full border backdrop-blur-md ${isPlaying ? 'bg-red-500/10 border-red-500/30 text-red-500' : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-500'}`}>
            <div className={`w-2 h-2 rounded-full ${isPlaying ? 'bg-red-500 animate-pulse' : 'bg-yellow-500'}`} />
            <span className="text-[10px] font-mono font-bold tracking-widest">{isPlaying ? 'LIVE REC' : 'PAUSED'}</span>
          </div>
        </div>
      </div>

      <CardContent className="flex-1 p-0 h-full relative">
        {/* Main Video Area */}
        <div className="relative w-full h-full min-h-[300px] bg-black flex items-center justify-center overflow-hidden">

          {/* Background Grid (When no video) */}
          <div className="absolute inset-0 opacity-10 bg-[linear-gradient(rgba(255,255,255,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.1)_1px,transparent_1px)] bg-[size:20px_20px]" />

          {/* Simulated Stream Content */}
          {activeType === 'Thermal' || activeType === 'RGB' ? (
            <div className="relative w-full h-full">
              <img
                src={getStreamUrl(activeType)}
                alt={`${activeType} Stream`}
                className="w-full h-full object-cover opacity-90"
                key={activeType} // Force re-render on switch
              />
              {/* False Color Overlay Mix (Only for Thermal) */}
              {activeType === 'Thermal' && (
                <div className="absolute inset-0 bg-gradient-to-t from-purple-900/20 via-transparent to-orange-500/10 mix-blend-overlay pointer-events-none" />
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-white/20 animate-pulse">
              <Video className="w-16 h-16 mb-4 opacity-50" />
              <p className="font-mono text-sm tracking-widest uppercase">Signal Offline</p>
            </div>
          )}

          {/* HUD Overlay (SVG) */}
          <div className="absolute inset-4 pointer-events-none z-10 border border-white/10 rounded-lg">
            {/* Corner Brackets */}
            <div className="absolute top-0 left-0 w-8 h-8 border-l-2 border-t-2 border-cyan-500/50 rounded-tl-lg" />
            <div className="absolute top-0 right-0 w-8 h-8 border-r-2 border-t-2 border-cyan-500/50 rounded-tr-lg" />
            <div className="absolute bottom-0 left-0 w-8 h-8 border-l-2 border-b-2 border-cyan-500/50 rounded-bl-lg" />
            <div className="absolute bottom-0 right-0 w-8 h-8 border-r-2 border-b-2 border-cyan-500/50 rounded-br-lg" />

            {/* Center Crosshair */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
              <div className="w-12 h-12 border border-white/20 rounded-full flex items-center justify-center">
                <div className="w-1 h-1 bg-cyan-400 rounded-full shadow-[0_0_10px_#22d3ee]" />
              </div>
              <div className="absolute top-1/2 left-0 w-full h-[1px] bg-cyan-500/20" />
              <div className="absolute left-1/2 top-0 h-full w-[1px] bg-cyan-500/20" />
            </div>

            {/* Data Readouts */}
            <div className="absolute bottom-4 left-4 font-mono text-[10px] text-cyan-500/60 leading-tight">
              <div>ISO: 800</div>
              <div>SHUTTER: 1/2000</div>
              <div>WB: 5600K</div>
            </div>
            <div className="absolute bottom-4 right-4 font-mono text-[10px] text-cyan-500/60 leading-tight text-right">
              <div>LAT: 34.0522 N</div>
              <div>LON: 118.2437 W</div>
              <div>ALT: 450 FT</div>
            </div>
          </div>

          {/* Control Bar (Bottom center hover) */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center space-x-4 px-6 py-2 bg-black/60 backdrop-blur-md rounded-full border border-white/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300 transform translate-y-2 group-hover:translate-y-0">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className="p-2 hover:bg-white/10 rounded-full text-white transition-colors"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <div className="w-[1px] h-4 bg-white/20" />
            <button className="p-2 hover:bg-white/10 rounded-full text-white transition-colors">
              <Maximize className="w-4 h-4" />
            </button>
            <button className="p-2 hover:bg-white/10 rounded-full text-white transition-colors">
              <Settings className="w-4 h-4" />
            </button>
          </div>

        </div>
      </CardContent>
    </Card>
  );
};