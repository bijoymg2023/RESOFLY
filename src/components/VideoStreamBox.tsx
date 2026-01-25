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
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

interface Capture {
  url: string;
  filename: string;
  timestamp: string;
}

type ViewMode = 'Live' | 'Gallery';

export const VideoStreamBox = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('Live');
  const [latestCapture, setLatestCapture] = useState<Capture | null>(null);
  const [gallery, setGallery] = useState<Capture[]>([]);
  const [isCapturing, setIsCapturing] = useState(false);
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
    try {
      // Trigger flash effect or sound here if desired
      const res = await fetch('/api/capture', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });

      if (res.ok) {
        const newCapture = await res.json();
        setLatestCapture(newCapture);
        setSelectedImage(newCapture);
        // Refresh gallery to include new image
        await fetchGallery();
      }
    } catch (e) {
      console.error("Capture failed", e);
    } finally {
      setIsCapturing(false);
    }
  };

  const getMainDisplayUrl = () => {
    if (selectedImage) return selectedImage.url;
    // Fallback placeholder if no images
    return "https://placehold.co/600x400/000000/333333?text=No+Captures";
  };

  return (
    <Card className="h-full bg-[#0A0A0A] border border-white/10 overflow-hidden relative group shadow-2xl flex flex-col">
      {/* Header / Toolbar */}
      <div className="absolute top-0 left-0 right-0 z-20 flex justify-between items-start p-4 bg-gradient-to-b from-black/90 to-transparent pointer-events-none">
        <div className="pointer-events-auto flex space-x-2">
          <div className="bg-black/40 backdrop-blur border border-white/10 rounded-md px-3 py-1 text-xs font-mono text-cyan-400">
            THERMAL SNAPSHOT MODE
          </div>
        </div>

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
      </div>

      <CardContent className="flex-1 p-0 h-full relative flex flex-col">
        {/* Main Viewer */}
        <div className="relative flex-1 bg-black flex items-center justify-center overflow-hidden">

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
            </div>
          )}

          {/* Flash Overlay */}
          {isCapturing && (
            <div className="absolute inset-0 bg-white animate-flash pointer-events-none z-50 mix-blend-overlay" />
          )}

          {/* HUD Overlay (Static) */}
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

          {/* Timestamp Info */}
          {selectedImage && (
            <div className="absolute bottom-6 right-6 text-right font-mono text-[10px] text-cyan-500/60 bg-black/60 px-2 py-1 rounded backdrop-blur">
              <div>FILE: {selectedImage.filename}</div>
              <div>TIME: {selectedImage.timestamp}</div>
            </div>
          )}
        </div>

        {/* Gallery Strip (Bottom) */}
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
      </CardContent>
    </Card>
  );
};