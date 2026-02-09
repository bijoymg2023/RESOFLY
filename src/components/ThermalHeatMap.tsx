import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useIsMobile } from '@/hooks/use-mobile';
import { Thermometer, TrendingUp, AlertTriangle } from 'lucide-react';

export const ThermalHeatMap = () => {
  const [temperatureData, setTemperatureData] = useState<number[][]>([]);
  const [maxTemp, setMaxTemp] = useState(42);
  const [minTemp, setMinTemp] = useState(18);
  const [avgTemp, setAvgTemp] = useState(28);
  const isMobile = useIsMobile();

  // Generate simulated thermal data with mobile-optimized grid size
  useEffect(() => {
    const generateHeatMapData = () => {
      const gridSize = isMobile ? 12 : 16; // Smaller grid on mobile
      const data = [];
      for (let i = 0; i < gridSize; i++) {
        const row = [];
        for (let j = 0; j < gridSize; j++) {
          // Create some interesting patterns
          const centerDistance = Math.sqrt(Math.pow(i - gridSize / 2, 2) + Math.pow(j - gridSize / 2, 2));
          const noise = (Math.random() - 0.5) * 8;
          const baseTemp = 25 + Math.sin(centerDistance * 0.5) * 10 + noise;
          row.push(Math.max(15, Math.min(45, baseTemp)));
        }
        data.push(row);
      }
      return data;
    };

    const updateData = () => {
      const newData = generateHeatMapData();
      setTemperatureData(newData);

      const flatData = newData.flat();
      setMaxTemp(Math.max(...flatData));
      setMinTemp(Math.min(...flatData));
      setAvgTemp(flatData.reduce((sum, temp) => sum + temp, 0) / flatData.length);
    };

    updateData();
    const interval = setInterval(updateData, 2000);
    return () => clearInterval(interval);
  }, [isMobile]);

  const getTemperatureColor = (temp: number) => {
    const normalized = (temp - 15) / (45 - 15);

    if (normalized < 0.3) {
      return `hsl(220, 100%, ${70 + normalized * 30}%)`;
    } else if (normalized < 0.7) {
      return `hsl(${60 - normalized * 60}, 100%, 70%)`;
    } else {
      return `hsl(${14}, ${100}%, ${50 + normalized * 20}%)`;
    }
  };

  const gridSize = isMobile ? 12 : 16;

  return (
    <Card className="bg-black/80 border border-white/10 overflow-hidden relative shadow-lg flex flex-col h-[400px]">
      {/* Background Grid */}
      <div className="absolute inset-0 opacity-10 bg-[linear-gradient(rgba(0,255,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,255,0.05)_1px,transparent_1px)] bg-[size:10px_10px] pointer-events-none" />

      <CardHeader className="py-3 px-4 border-b border-white/5 bg-white/[0.02]">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center text-xs font-mono uppercase tracking-widest text-white/80">
            <Thermometer className="w-4 h-4 mr-2" />
            {isMobile ? 'Heat Map' : 'Thermal Heat Map'}
          </CardTitle>
          <Badge variant="outline" className="bg-red-500/10 text-red-500 border-red-500/20 text-[10px] font-mono animate-pulse">
            <TrendingUp className="w-3 h-3 mr-1" />
            LIVE
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col p-4 relative z-10">
        {/* Temperature Stats */}
        <div className="grid grid-cols-3 gap-2 mb-4 flex-shrink-0">
          <div className="text-center p-2 bg-white/5 rounded border border-white/10">
            <p className="text-[9px] text-white/40 uppercase tracking-wider mb-1">Min</p>
            <p className="text-xs font-bold text-cyan-400 font-mono">{minTemp.toFixed(1)}°C</p>
          </div>
          <div className="text-center p-2 bg-white/5 rounded border border-white/10">
            <p className="text-[9px] text-white/40 uppercase tracking-wider mb-1">Avg</p>
            <p className="text-xs font-bold text-white font-mono">{avgTemp.toFixed(1)}°C</p>
          </div>
          <div className="text-center p-2 bg-white/5 rounded border border-white/10">
            <p className="text-[9px] text-white/40 uppercase tracking-wider mb-1">Max</p>
            <p className="text-xs font-bold text-red-500 font-mono">{maxTemp.toFixed(1)}°C</p>
          </div>
        </div>

        {/* Heat Map Grid */}
        <div className="flex-1 flex items-center justify-center p-2 border border-white/5 bg-black/50 rounded-lg shadow-inner overflow-hidden relative">

          {/* Scanline */}
          <div className="absolute top-0 left-0 w-full h-[2px] bg-cyan-500/30 animate-scan pointer-events-none z-20 shadow-[0_0_10px_rgba(34,211,238,0.5)]" />

          <div
            className={`grid gap-[2px]`}
            style={{
              gridTemplateColumns: `repeat(${gridSize}, 1fr)`,
              gridTemplateRows: `repeat(${gridSize}, 1fr)`,
              width: '100%',
              maxWidth: '240px',
              aspectRatio: '1/1'
            }}
          >
            {temperatureData.map((row, i) =>
              row.map((temp, j) => (
                <div
                  key={`${i}-${j}`}
                  className="rounded-[1px] transition-colors duration-500 relative"
                  style={{
                    backgroundColor: getTemperatureColor(temp),
                    opacity: 0.9
                  }}
                  title={`${temp.toFixed(1)}°C`}
                />
              ))
            )}
          </div>
        </div>

        {/* Temperature Scale */}
        <div className="mt-4 flex-shrink-0">
          <div className="flex justify-between text-[9px] text-white/30 mb-1 uppercase tracking-wider font-mono">
            <span>Cool</span>
            <span>Hot</span>
          </div>
          <div
            className="h-1 rounded-full relative"
            style={{
              background: 'linear-gradient(to right, hsl(220, 100%, 70%), hsl(60, 100%, 70%), hsl(14, 100%, 70%))'
            }}
          >
            {/* Indicator for Avg Temp */}
            <div
              className="absolute top-1/2 -translate-y-1/2 w-2 h-2 bg-white border border-black rounded-full shadow-lg transition-all duration-1000"
              style={{ left: `${((avgTemp - 15) / (45 - 15)) * 100}%` }}
            />
          </div>
          <div className="flex justify-between text-[9px] text-white/30 mt-1 font-mono">
            <span>15°C</span>
            <span>45°C</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};