import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
    AlertTriangle,
    Flame,
    Users,
    Thermometer,
    MapPin,
    Clock
} from 'lucide-react';

interface DetectionAlert {
    id: string;
    type: 'person' | 'fire' | 'temperature' | 'location';
    message: string;
    timestamp: Date;
    data?: {
        count?: number;
        temp?: number;
        lat?: number;
        lng?: number;
    };
}

const alertConfig = {
    person: { icon: Users, color: 'text-blue-400', bg: 'bg-blue-500/10' },
    fire: { icon: Flame, color: 'text-red-500', bg: 'bg-red-500/10' },
    temperature: { icon: Thermometer, color: 'text-orange-400', bg: 'bg-orange-500/10' },
    location: { icon: MapPin, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
};

// Dummy data generator
const generateDummyAlerts = (): DetectionAlert[] => {
    const now = new Date();
    return [
        {
            id: '1',
            type: 'person',
            message: '3 people detected in Zone A',
            timestamp: new Date(now.getTime() - 30000),
            data: { count: 3 }
        },
        {
            id: '2',
            type: 'fire',
            message: 'Heat signature detected - Sector 7',
            timestamp: new Date(now.getTime() - 120000),
        },
        {
            id: '3',
            type: 'temperature',
            message: 'High temp: 67.2°C',
            timestamp: new Date(now.getTime() - 180000),
            data: { temp: 67.2 }
        },
        {
            id: '4',
            type: 'location',
            message: 'GPS: 12.9716°N, 77.5946°E',
            timestamp: new Date(now.getTime() - 300000),
            data: { lat: 12.9716, lng: 77.5946 }
        },
        {
            id: '5',
            type: 'person',
            message: '1 person detected in Zone B',
            timestamp: new Date(now.getTime() - 420000),
            data: { count: 1 }
        },
        {
            id: '6',
            type: 'fire',
            message: 'Potential fire risk - Quadrant 4',
            timestamp: new Date(now.getTime() - 600000),
        },
    ];
};

export const AlertsDetectionBox = () => {
    const [alerts, setAlerts] = useState<DetectionAlert[]>([]);

    useEffect(() => {
        // Initialize with dummy data
        setAlerts(generateDummyAlerts());

        // Simulate new alerts coming in periodically
        const interval = setInterval(() => {
            const types: DetectionAlert['type'][] = ['person', 'fire', 'temperature', 'location'];
            const randomType = types[Math.floor(Math.random() * types.length)];

            const newAlert: DetectionAlert = {
                id: Date.now().toString(),
                type: randomType,
                message: randomType === 'person'
                    ? `${Math.floor(Math.random() * 5) + 1} people detected`
                    : randomType === 'fire'
                        ? 'Heat signature detected'
                        : randomType === 'temperature'
                            ? `Temp: ${(Math.random() * 30 + 40).toFixed(1)}°C`
                            : `GPS: ${(Math.random() * 0.1 + 12.9).toFixed(4)}°N, ${(Math.random() * 0.1 + 77.5).toFixed(4)}°E`,
                timestamp: new Date(),
            };

            setAlerts(prev => [newAlert, ...prev.slice(0, 9)]);
        }, 8000);

        return () => clearInterval(interval);
    }, []);

    return (
        <Card className="bg-[#0A0A0A]/90 border border-white/10 backdrop-blur-sm flex flex-col overflow-hidden shadow-xl h-full min-h-[280px]">
            <CardHeader className="py-3 px-4 border-b border-white/5 bg-black/40 flex flex-row items-center justify-between">
                <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    <CardTitle className="text-xs font-mono uppercase tracking-widest text-white/60">Alerts</CardTitle>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono border-red-500/20 text-red-400 bg-red-500/10">
                    {alerts.length} ACTIVE
                </Badge>
            </CardHeader>

            <CardContent className="flex-1 p-0 bg-black/50 font-mono text-xs overflow-hidden relative">
                {/* CRT Scanline Effect */}
                <div className="absolute inset-0 pointer-events-none z-10 opacity-5 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))]" style={{ backgroundSize: "100% 2px, 3px 100%" }} />

                <ScrollArea className="flex-1 w-full">
                    <div className="space-y-1">
                        {alerts.length === 0 ? (
                            <div className="text-white/20 italic p-2 text-center text-xs">
                                <span>{'>'} No active alerts...</span>
                            </div>
                        ) : (
                            alerts.map((alert) => {
                                const config = alertConfig[alert.type];
                                const Icon = config.icon;
                                return (
                                    <div
                                        key={alert.id}
                                        className="group flex items-start space-x-3 p-2 hover:bg-white/5 rounded transition-colors cursor-default"
                                    >
                                        <span className="text-white/30 shrink-0 font-mono text-xs">
                                            {alert.timestamp.toLocaleTimeString([], { hour12: false })}
                                        </span>
                                        <span className={`shrink-0 ${config.color}`}>
                                            <Icon className="w-3 h-3" />
                                        </span>
                                        <span className="text-white/80 flex-1 truncate text-xs">
                                            {alert.message}
                                        </span>
                                    </div>
                                );
                            })
                        )}
                        <div className="text-white/20 pt-2 animate-pulse">_</div>
                    </div>
                </ScrollArea>
            </CardContent>
        </Card>
    );
};
