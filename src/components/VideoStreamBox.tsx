import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import {
  Camera,
  Layers,
  Image as ImageIcon,
  ScanLine,
  Video,
  Thermometer,
  AlertCircle,
  RefreshCw,
  Radio,
  Grid
} from 'lucide-react';

interface Capture {
  url: string;
  filename: string;
  timestamp: string;
}

type VideoType = 'RGB' | 'Thermal';

/**
 * RGBStreamView - Native MJPEG stream for maximum FPS
 * Uses the browser's built-in MJPEG decoder which is far faster
 * than manual frame polling (no per-frame HTTP overhead).
 */
const RGBStreamView = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [hasError, setHasError] = useState(false);

  return (
    <div className="relative w-full h-full bg-transparent">
      {!hasError ? (
        <img
          src="/api/stream/rgb"
          alt="Live RGB Feed"
          className="w-full h-full object-contain"
          onLoad={() => setIsConnected(true)}
          onError={() => { setHasError(true); setIsConnected(false); }}
        />
      ) : (
        <div className="flex flex-col items-center justify-center h-full text-white/40 font-mono">
          <AlertCircle className="w-12 h-12 mb-3 text-red-500/50" />
          <p className="text-xs tracking-widest text-red-400">STREAM OFFLINE</p>
          <button
            onClick={() => setHasError(false)}
            className="mt-4 px-4 py-2 bg-white/10 rounded text-xs hover:bg-white/20"
          >
            Retry
          </button>
        </div>
      )}

      {/* Live Indicator */}
      <div className="absolute top-4 right-4 flex items-center space-x-2 bg-black/60 px-2 py-1 rounded backdrop-blur z-20 border border-white/5">
        <div className={`w-2 h-2 rounded-full animate-pulse ${isConnected ? 'bg-green-500' : 'bg-yellow-500'}`} />
        <span className={`font-mono text-[9px] ${isConnected ? 'text-green-400' : 'text-yellow-400'}`}>
          {isConnected ? 'LIVE' : 'CONNECTING'}
        </span>
      </div>
    </div>
  );
};

export const VideoStreamBox = () => {
  const [activeType, setActiveType] = useState<VideoType>('Thermal');
  const [streamError, setStreamError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  // Live Waveshare thermal MJPEG stream from backend pipeline
  const THERMAL_STREAM_URL = `/thermal/`;

  // Handle stream errors
  const handleStreamError = () => {
    setStreamError(true);
  };

  const handleStreamLoad = () => {
    setStreamError(false);
  };

  const videoTypes = [
    { key: 'RGB' as VideoType, label: 'OPTICAL', icon: Video },
    { key: 'Thermal' as VideoType, label: 'THERMAL', icon: Thermometer }
  ];

  return (
    <Card className="h-full bg-card dark:bg-black border border-border dark:border-white/10 overflow-hidden relative group shadow-2xl flex flex-col rounded-xl">
      {/* Header / Tabs */}
      <div className="relative z-20 flex justify-between items-start p-4 bg-muted/50 dark:bg-[#0A0A0A] border-b border-border dark:border-white/5">
        {/* Stream Type Tabs */}
        <div className="flex space-x-1 bg-muted dark:bg-black/60 p-1 rounded-lg border border-border dark:border-white/10">
          {videoTypes.map((type) => (
            <button
              key={type.key}
              onClick={() => setActiveType(type.key)}
              className={`
                        px-3 py-1.5 rounded-md text-[10px] font-bold tracking-wider flex items-center space-x-2 transition-all duration-300
                        ${activeType === type.key
                  ? 'bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 border border-cyan-500/50 shadow-[0_0_10px_rgba(34,211,238,0.15)]'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent/10 dark:hover:bg-white/5 border border-transparent'}
                    `}
            >
              <type.icon className="w-3 h-3" />
              <span className="hidden sm:inline">{type.label}</span>
            </button>
          ))}
        </div>

        {/* Actions (Only in Thermal) - Removed Gallery/Capture buttons as requested */}
      </div>

      <CardContent className="flex-1 p-0 h-full relative flex flex-col bg-white dark:bg-[#050505] transition-colors duration-300">
        {/* Content Area */}
        <div className="relative flex-1 flex items-center justify-center overflow-hidden">

          {/* Background Grid */}
          <div className="absolute inset-0 opacity-10 bg-[linear-gradient(rgba(0,0,0,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.1)_1px,transparent_1px)] dark:bg-[linear-gradient(rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[size:40px_40px]" />

          {activeType === 'Thermal' ? (
            <>
              {/* LIVE STREAM MODE ONLY */}
              <>
                {streamError ? (
                  <div className="text-white/30 font-mono flex flex-col items-center z-10">
                    <AlertCircle className="w-16 h-16 mb-4 text-red-500/50" />
                    <p className="tracking-widest text-xs text-red-400">STREAM OFFLINE</p>
                    <p className="text-[10px] mt-2 text-white/30">Check thermal camera connection</p>
                    <button
                      onClick={() => setStreamError(false)}
                      className="mt-4 px-4 py-2 bg-white/10 rounded text-xs hover:bg-white/20"
                    >
                      Retry Connection
                    </button>
                  </div>
                ) : (
                  <img
                    ref={imgRef}
                    src={THERMAL_STREAM_URL}
                    alt="Live Thermal Feed"
                    onLoad={handleStreamLoad}
                    onError={handleStreamError}
                    className="w-full h-full object-contain"
                  />
                )}

                {/* Live Indicator */}
                {!streamError && (
                  <div className="absolute top-20 right-4 flex items-center space-x-2 bg-black/60 px-2 py-1 rounded backdrop-blur z-20 border border-white/5">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="font-mono text-[9px] text-green-400">LIVE THERMAL</span>
                  </div>
                )}
              </>
            </>
          ) : (
            /* RGB Camera Stream from Pi Camera - Rapid Frame Polling */
            <RGBStreamView />
          )}

          {/* HUD Overlay */}
          {activeType === 'Thermal' && (
            <div className="absolute inset-4 pointer-events-none z-10 border border-white/5 rounded-lg opacity-30">
              <div className="absolute top-0 left-0 w-4 h-4 border-l-2 border-t-2 border-cyan-500/30" />
              <div className="absolute top-0 right-0 w-4 h-4 border-r-2 border-t-2 border-cyan-500/30" />
              <div className="absolute bottom-0 left-0 w-4 h-4 border-l-2 border-b-2 border-cyan-500/30" />
              <div className="absolute bottom-0 right-0 w-4 h-4 border-r-2 border-b-2 border-cyan-500/30" />

              {/* Center Crosshair */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-20">
                <div className="w-8 h-8 border border-white/50 rounded-full flex items-center justify-center">
                  <div className="w-0.5 h-0.5 bg-cyan-400" />
                </div>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};