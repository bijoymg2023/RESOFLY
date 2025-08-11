import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Thermometer, TrendingUp, AlertTriangle } from 'lucide-react';

export const ThermalHeatMap = () => {
  const [temperatureData, setTemperatureData] = useState<number[][]>([]);
  const [maxTemp, setMaxTemp] = useState(42);
  const [minTemp, setMinTemp] = useState(18);
  const [avgTemp, setAvgTemp] = useState(28);

  // Generate simulated thermal data
  useEffect(() => {
    const generateHeatMapData = () => {
      const data = [];
      for (let i = 0; i < 16; i++) {
        const row = [];
        for (let j = 0; j < 16; j++) {
          // Create some interesting patterns
          const centerDistance = Math.sqrt(Math.pow(i - 8, 2) + Math.pow(j - 8, 2));
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
  }, []);

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

  return (
    <Card className="h-full bg-dashboard-panel border-dashboard-panel-border">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center text-lg">
            <Thermometer className="w-5 h-5 mr-2" />
            Thermal Heat Map
          </CardTitle>
          <Badge variant="outline" className="bg-thermal/20 text-thermal border-thermal/30">
            <TrendingUp className="w-3 h-3 mr-1" />
            Live
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col overflow-hidden">
        {/* Temperature Stats */}
        <div className="grid grid-cols-3 gap-2 mb-3 flex-shrink-0">
          <div className="text-center">
            <p className="text-xs text-muted-foreground">Min</p>
            <p className="text-sm font-bold text-primary">{minTemp.toFixed(1)}°C</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground">Avg</p>
            <p className="text-sm font-bold text-foreground">{avgTemp.toFixed(1)}°C</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground">Max</p>
            <p className="text-sm font-bold text-thermal">{maxTemp.toFixed(1)}°C</p>
          </div>
        </div>

        {/* Heat Map Grid */}
        <div className="flex-1 bg-muted/10 rounded-lg p-3 border border-dashboard-panel-border overflow-hidden">
          <div 
            className="grid gap-0.5 h-full w-full max-h-[240px] max-w-[240px] mx-auto aspect-square"
            style={{ gridTemplateColumns: 'repeat(16, 1fr)', gridTemplateRows: 'repeat(16, 1fr)' }}
          >
            {temperatureData.map((row, i) =>
              row.map((temp, j) => (
                <div
                  key={`${i}-${j}`}
                  className="rounded-sm transition-all duration-300 hover:scale-110 hover:z-10 relative group"
                  style={{
                    backgroundColor: getTemperatureColor(temp),
                  }}
                  title={`${temp.toFixed(1)}°C`}
                >
                  <div className="absolute inset-0 bg-background/0 group-hover:bg-background/20 rounded-sm" />
                </div>
              ))
            )}
          </div>
        </div>

        {/* Temperature Scale */}
        <div className="mt-3 flex-shrink-0">
          <div className="flex justify-between text-xs text-muted-foreground mb-1">
            <span>Cool</span>
            <span>Hot</span>
          </div>
          <div 
            className="h-1.5 rounded-full"
            style={{
              background: 'linear-gradient(to right, hsl(220, 100%, 70%), hsl(60, 100%, 70%), hsl(14, 100%, 70%))'
            }}
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>15°C</span>
            <span>45°C</span>
          </div>
        </div>

        {/* Alert for high temperatures */}
        {maxTemp > 40 && (
          <div className="mt-2 p-2 bg-warning/20 border border-warning/30 rounded-lg flex-shrink-0">
            <div className="flex items-center text-warning">
              <AlertTriangle className="w-3 h-3 mr-2" />
              <span className="text-xs font-medium">High temperature detected</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};