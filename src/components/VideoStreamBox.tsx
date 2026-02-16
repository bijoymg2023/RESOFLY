import React, { useState, useEffect, useRef, useCallback } from 'react';
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

type VideoType = 'RGB' | 'Thermal' | 'Overlay';
type ThermalMode = 'live' | 'gallery';

/**
 * StreamView — Self-cleaning MJPEG stream component.
 *
 * CRITICAL: On unmount this sets img.src = "" which aborts the
 * underlying HTTP chunked-transfer connection. Without this,
 * switching tabs leaves zombie MJPEG connections alive causing
 * overlapping frames and resource leaks.
 */
const StreamView = ({ src, label }: { src: string; label: string }) => {
  const imgRef = useRef<HTMLImageElement>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [hasError, setHasError] = useState(false);

  // Cleanup: abort MJPEG connection on unmount
  useEffect(() => {
    return () => {
      if (imgRef.current) {
        imgRef.current.src = ''; // Kill HTTP connection
      }
    };
  }, []);

  const retry = useCallback(() => {
    setHasError(false);
    setIsConnected(false);
    // Force re-fetch by appending cache-buster
    if (imgRef.current) {
      imgRef.current.src = '';
      setTimeout(() => {
        if (imgRef.current) {
          imgRef.current.src = `${src}?t=${Date.now()}`;
        }
      }, 100);
    }
  }, [src]);

  return (
    <div className="relative w-full h-full bg-black">
      {!hasError ? (
        <img
          ref={imgRef}
          src={src}
          alt={`Live ${label} Feed`}
          className="w-full h-full object-contain"
          onLoad={() => setIsConnected(true)}
          onError={() => { setHasError(true); setIsConnected(false); }}
        />
      ) : (
        <div className="flex flex-col items-center justify-center h-full text-white/40 font-mono">
          <AlertCircle className="w-12 h-12 mb-3 text-red-500/50" />
          <p className="text-xs tracking-widest text-red-400">STREAM OFFLINE</p>
          <p className="text-[10px] mt-2 text-white/30">Check {label.toLowerCase()} camera connection</p>
          <button
            onClick={retry}
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
          {isConnected ? `LIVE ${label}` : 'CONNECTING'}
        </span>
      </div>
    </div>
  );
};

export const VideoStreamBox = () => {
  const [activeType, setActiveType] = useState<VideoType>('Thermal');
  const [thermalMode, setThermalMode] = useState<ThermalMode>('live');
  const [latestCapture, setLatestCapture] = useState<Capture | null>(null);
  const [gallery, setGallery] = useState<Capture[]>([]);
  const [isCapturing, setIsCapturing] = useState(false);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const { token } = useAuth();
  const [selectedImage, setSelectedImage] = useState<Capture | null>(null);

  // Live Waveshare thermal MJPEG stream from backend pipeline
  const THERMAL_STREAM_URL = `/thermal/`;

  // Fetch gallery on mount
  useEffect(() => {
    fetchGallery();
  }, [token]);

  const fetchGallery = async () => {
    try {
      const res = await fetch('/api/gallery', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setGallery(data);
        if (data.length > 0 && !selectedImage) {
          setSelectedImage(data[0]);
        }
      }
    } catch (e) {
      console.error("Failed to fetch gallery", e);
    }
  };

  const handleCapture = async () => {
    setIsCapturing(true);
    setCaptureError(null);
    try {
      const res = await fetch('/api/capture', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });

      if (res.ok) {
        const newCapture = await res.json();
        setLatestCapture(newCapture);
        setSelectedImage(newCapture);
        await fetchGallery();
        // Switch to gallery to show the captured image
        setThermalMode('gallery');
      } else {
        const err = await res.json();
        setCaptureError(err.detail || "Capture Failed");
      }
    } catch (e) {
      setCaptureError("Connection Error");
      console.error("Capture failed", e);
    } finally {
      setIsCapturing(false);
    }
  };

  const handleCalibrate = async () => {
    setIsCalibrating(true);
    try {
      await fetch('/api/calibrate', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      setTimeout(() => setIsCalibrating(false), 2000);
    } catch (e) {
      setIsCalibrating(false);
    }
  };

  const videoTypes = [
    { key: 'RGB' as VideoType, label: 'OPTICAL', icon: Video },
    { key: 'Thermal' as VideoType, label: 'THERMAL', icon: Thermometer },
    { key: 'Overlay' as VideoType, label: 'FUSION', icon: Layers }
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

        {/* Actions (Only in Thermal) */}
        {activeType === 'Thermal' && (
          <div className="pointer-events-auto flex space-x-2">
            {/* Live/Gallery Toggle */}
            <div className="flex bg-muted dark:bg-black/40 rounded-md border border-border dark:border-white/20 overflow-hidden">
              <button
                onClick={() => setThermalMode('live')}
                className={`px-2 py-1 text-[9px] flex items-center space-x-1 ${thermalMode === 'live' ? 'bg-green-500/20 text-green-600 dark:text-green-400' : 'text-muted-foreground'}`}
              >
                <Radio className="w-3 h-3" />
                <span>LIVE</span>
              </button>
              <button
                onClick={() => setThermalMode('gallery')}
                className={`px-2 py-1 text-[9px] flex items-center space-x-1 ${thermalMode === 'gallery' ? 'bg-purple-500/20 text-purple-600 dark:text-purple-400' : 'text-muted-foreground'}`}
              >
                <Grid className="w-3 h-3" />
                <span>GALLERY</span>
              </button>
            </div>

            {/* Calibrate Button */}
            <Button
              onClick={handleCalibrate}
              disabled={isCalibrating || isCapturing}
              size="sm"
              variant="outline"
              className={`border-border dark:border-white/20 bg-muted dark:bg-black/40 text-cyan-600 dark:text-cyan-500 hover:text-cyan-500 dark:hover:text-cyan-400 text-[10px] h-8 ${isCalibrating ? 'animate-pulse border-cyan-500' : ''}`}
            >
              <RefreshCw className={`w-3 h-3 mr-2 ${isCalibrating ? 'animate-spin' : ''}`} />
              {isCalibrating ? 'CALIBRATING' : 'FFC'}
            </Button>

            {/* Capture Button */}
            <Button
              onClick={handleCapture}
              disabled={isCapturing}
              size="sm"
              className={`bg-red-600 hover:bg-red-500 text-white font-bold tracking-wider border border-red-400/30 shadow-[0_0_15px_rgba(220,38,38,0.5)] transition-all h-8 ${isCapturing ? 'opacity-50' : ''}`}
            >
              <Camera className={`w-3 h-3 mr-2 ${isCapturing ? 'animate-pulse' : ''}`} />
              {isCapturing ? 'CAPTURING' : 'CAPTURE'}
            </Button>
          </div>
        )}
      </div>

      <CardContent className="flex-1 p-0 h-full relative flex flex-col bg-neutral-900 dark:bg-[#050505]">
        {/* Content Area */}
        <div className="relative flex-1 flex items-center justify-center overflow-hidden">

          {/* Background Grid */}
          <div className="absolute inset-0 opacity-10 bg-[linear-gradient(rgba(128,128,128,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(128,128,128,0.05)_1px,transparent_1px)] bg-[size:40px_40px]" />

          {activeType === 'Thermal' ? (
            <>
              {/* LIVE STREAM MODE */}
              {thermalMode === 'live' ? (
                /* key forces full remount → kills old MJPEG connection */
                <StreamView key="thermal-live" src={THERMAL_STREAM_URL} label="THERMAL" />
              ) : (
                /* GALLERY MODE */
                <>
                  {selectedImage ? (
                    <img
                      src={selectedImage.url}
                      alt="Selected Thermal Capture"
                      className="w-full h-full object-contain transition-opacity duration-300"
                    />
                  ) : (
                    <div className="text-white/30 font-mono flex flex-col items-center z-10">
                      <ImageIcon className="w-16 h-16 mb-4 opacity-10" />
                      <p className="tracking-widest text-xs">NO IMAGES CAPTURED</p>
                      {captureError && (
                        <div className="mt-4 text-red-500 bg-red-500/10 px-4 py-2 rounded border border-red-500/20 flex items-center text-xs">
                          <AlertCircle className="w-3 h-3 mr-2" />
                          {captureError}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Timestamp Info */}
                  {selectedImage && (
                    <div className="absolute top-20 right-4 text-right font-mono text-[9px] text-cyan-500/60 bg-black/60 px-2 py-1 rounded backdrop-blur z-20 border border-white/5">
                      <div>ID: {selectedImage.filename.substring(8, 20)}...</div>
                      <div>TS: {selectedImage.timestamp}</div>
                    </div>
                  )}

                  {/* Gallery Strip */}
                  <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-black via-black/80 to-transparent flex items-end px-4 pb-4 space-x-2 overflow-x-auto z-30 scrollbar-none">
                    {gallery.map((img) => (
                      <button
                        key={img.filename}
                        onClick={() => setSelectedImage(img)}
                        className={`relative h-12 w-16 min-w-[64px] rounded border overflow-hidden transition-all hover:scale-110 hover:border-white ${selectedImage?.filename === img.filename ? 'border-cyan-500 opacity-100 ring-1 ring-cyan-500/50' : 'border-white/10 opacity-50 grayscale hover:grayscale-0'}`}
                      >
                        <img src={img.url} alt="thumbnail" className="w-full h-full object-cover" />
                      </button>
                    ))}
                  </div>
                </>
              )}

              {/* Flash Overlay */}
              {isCapturing && (
                <div className="absolute inset-0 bg-white animate-flash pointer-events-none z-50 mix-blend-overlay" />
              )}

              {/* Calibration Overlay */}
              {isCalibrating && (
                <div className="absolute inset-0 bg-black/80 z-40 flex items-center justify-center backdrop-blur-sm">
                  <div className="text-cyan-500 font-mono text-sm animate-pulse tracking-widest">
                    CALIBRATING SENSOR...
                  </div>
                </div>
              )}
            </>
          ) : activeType === 'RGB' ? (
            /* RGB Camera Stream — key forces clean remount on switch */
            <StreamView key="rgb-live" src="/api/stream/rgb" label="OPTICAL" />
          ) : (
            /* Offline / Placeholder for Fusion */
            <div className="flex flex-col items-center justify-center h-full w-full bg-black relative overflow-hidden">
              <div className="absolute inset-0 opacity-5 bg-[url('https://upload.wikimedia.org/wikipedia/commons/7/76/Noise_tv.gif')] bg-repeat opacity-10 mix-blend-overlay pointer-events-none" />

              <div className="z-10 flex flex-col items-center">
                <div className="relative mb-6">
                  <Layers className="w-16 h-16 text-yellow-900/40" />
                  <ScanLine className="absolute inset-0 w-16 h-16 text-white/5 animate-scan" />
                </div>

                <div className="flex items-center space-x-2 px-4 py-1 bg-white/5 rounded border border-white/10 backdrop-blur">
                  <div className="w-2 h-2 rounded-full animate-pulse bg-yellow-500" />
                  <span className="font-mono text-xl font-bold tracking-[0.2em] text-white/40">NO SIGNAL</span>
                </div>
                <p className="font-mono text-[9px] text-white/20 mt-3 tracking-widest uppercase">
                  Fusion Sensor Unavailable
                </p>
              </div>
            </div>
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