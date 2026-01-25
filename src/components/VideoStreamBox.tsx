import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import {
  Camera,
  Layers,
  Image as ImageIcon,
  Maximize,
  Settings,
  Video,
  Thermometer,
  Play,
  Pause,
  AlertCircle
} from 'lucide-react';

interface Capture {
  url: string;
  filename: string;
  timestamp: string;
}

type VideoType = 'RGB' | 'Thermal' | 'Overlay';

export const VideoStreamBox = () => {
  const [activeType, setActiveType] = useState<VideoType>('Thermal');
  const [latestCapture, setLatestCapture] = useState<Capture | null>(null);
  const [gallery, setGallery] = useState<Capture[]>([]);
  const [isCapturing, setIsCapturing] = useState(false);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const { token } = useAuth();
  const [selectedImage, setSelectedImage] = useState<Capture | null>(null);

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

  const videoTypes = [
    { key: 'RGB' as VideoType, label: 'OPTICAL', icon: Video },
    { key: 'Thermal' as VideoType, label: 'THERMAL', icon: Thermometer },
    { key: 'Overlay' as VideoType, label: 'FUSION', icon: Layers }
  ];

  return (
    <Card className="h-full bg-[#0A0A0A] border border-white/10 overflow-hidden relative group shadow-2xl flex flex-col">
      {/* Header / Tabs */}
      <div className="absolute top-0 left-0 right-0 z-20 flex justify-between items-start p-4 bg-gradient-to-b from-black/90 to-transparent pointer-events-none">
        {/* Stream Type Tabs */}
        <div className="pointer-events-auto flex space-x-1 bg-black/50 backdrop-blur-md p-1 rounded-lg border border-white/10">
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

        {/* Capture Action (Only in Thermal) */}
        {activeType === 'Thermal' && (
          <div className="pointer-events-auto">
            <Button
              onClick={handleCapture}
              disabled={isCapturing}
              className={`bg-red-600 hover:bg-red-500 text-white font-bold tracking-wider border border-red-400/30 shadow-[0_0_15px_rgba(220,38,38,0.5)] transition-all ${isCapturing ? 'opacity-50' : ''}`}
            >
              <Camera className={`w-4 h-4 mr-2 ${isCapturing ? 'animate-pulse' : ''}`} />
              {isCapturing ? 'CAPTURING...' : 'CAPTURE'}
            </Button>
          </div>
        )}
      </div>

      <CardContent className="flex-1 p-0 h-full relative flex flex-col">
        {/* Content Area */}
        <div className="relative flex-1 bg-black flex items-center justify-center overflow-hidden">

          {activeType === 'Thermal' ? (
            <>
              {/* Main Image */}
              {selectedImage ? (
                <img
                  src={selectedImage.url}
                  alt="Selected Thermal Capture"
                  className="w-full h-full object-contain transition-opacity duration-300"
                />
              ) : (
                <div className="text-white/30 font-mono flex flex-col items-center">
                  <ImageIcon className="w-12 h-12 mb-4 opacity-20" />
                  <p>NO IMAGES CAPTURED</p>
                  {captureError && (
                    <div className="mt-4 text-red-500 bg-red-500/10 px-4 py-2 rounded border border-red-500/20 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-2" />
                      {captureError}
                    </div>
                  )}
                </div>
              )}

              {/* Flash Overlay */}
              {isCapturing && (
                <div className="absolute inset-0 bg-white animate-flash pointer-events-none z-50 mix-blend-overlay" />
              )}

              {/* Timestamp Info */}
              {selectedImage && (
                <div className="absolute bottom-6 right-6 text-right font-mono text-[10px] text-cyan-500/60 bg-black/60 px-2 py-1 rounded backdrop-blur z-20">
                  <div>FILE: {selectedImage.filename}</div>
                  <div>TIME: {selectedImage.timestamp}</div>
                </div>
              )}
            </>
          ) : (
            /* Offline / Placeholder for RGB/Fusion */
            <div className="flex flex-col items-center justify-center h-full bg-black">
              <div className="relative">
                {activeType === 'RGB' ? <Video className="w-20 h-20 text-red-500/20" /> : <Layers className="w-20 h-20 text-yellow-500/20" />}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className={`w-16 h-[2px] rotate-45 ${activeType === 'RGB' ? 'bg-red-500/50' : 'bg-yellow-500/50'}`} />
                </div>
              </div>
              <p className={`font-mono text-2xl font-bold mt-6 tracking-[0.3em] ${activeType === 'RGB' ? 'text-red-500/80' : 'text-yellow-500/80'}`}>
                OFFLINE
              </p>
              <p className="font-mono text-[10px] text-white/30 mt-2 tracking-widest">{activeType === 'RGB' ? 'OPTICAL SENSOR' : 'FUSION MODE'}</p>
            </div>
          )}

          {/* HUD Overlay (Static - Always visible on Thermal) */}
          {activeType === 'Thermal' && (
            <div className="absolute inset-4 pointer-events-none z-10 border border-white/5 rounded-lg opacity-50">
              <div className="absolute top-0 left-0 w-4 h-4 border-l border-t border-cyan-500/30" />
              <div className="absolute top-0 right-0 w-4 h-4 border-r border-t border-cyan-500/30" />
              <div className="absolute bottom-0 left-0 w-4 h-4 border-l border-b border-cyan-500/30" />
              <div className="absolute bottom-0 right-0 w-4 h-4 border-r border-b border-cyan-500/30" />

              {/* Crosshair */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-20">
                <div className="w-8 h-8 border border-white/50 rounded-full" />
                <div className="w-1 h-1 bg-cyan-400 rounded-full absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
              </div>
            </div>
          )}
        </div>

        {/* Gallery Strip (Bottom - Only for Thermal) */}
        {activeType === 'Thermal' && (
          <div className="h-24 bg-black/90 border-t border-white/10 flex items-center px-4 space-x-2 overflow-x-auto scrollbar-thin scrollbar-thumb-white/20">
            {gallery.length === 0 && (
              <span className="text-xs text-white/20 font-mono w-full text-center">GALLERY EMPTY</span>
            )}
            {gallery.map((img) => (
              <button
                key={img.filename}
                onClick={() => setSelectedImage(img)}
                className={`relative h-20 min-w-[100px] border-2 rounded overflow-hidden transition-all ${selectedImage?.filename === img.filename ? 'border-cyan-500 opacity-100 scale-105' : 'border-transparent opacity-50 hover:opacity-100'}`}
              >
                <img src={img.url} alt="thumbnail" className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};