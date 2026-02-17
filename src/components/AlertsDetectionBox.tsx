import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
    Activity,
    Flame,
    Users,
    Thermometer,
    MapPin,
    Target,
    X,
    Trash2
} from 'lucide-react';
import { useDetection, DetectionEvent } from '@/contexts/DetectionContext';

const alertConfig = {
    LIFE: { icon: Activity, color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/50' },
    FIRE: { icon: Flame, color: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/50' },
    vehicle: { icon: Users, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30' },
    other: { icon: Target, color: 'text-white/50 dark:text-white/50', bg: 'bg-muted/30 dark:bg-white/5', border: 'border-border dark:border-white/10' },
};

export const AlertsDetectionBox = () => {
    const { activeAlerts, focusAlert, ackAlert, dismissAllAlerts } = useDetection();

    return (
        <Card className="bg-card/90 dark:bg-[#0A0A0A]/90 border border-border dark:border-white/10 backdrop-blur-sm flex flex-col overflow-hidden shadow-xl h-full">
            {/* Header */}
            <CardHeader className="py-3 px-4 border-b border-border dark:border-white/5 bg-muted/30 dark:bg-black/40 flex flex-row items-center justify-between shrink-0">
                <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    <CardTitle className="text-xs font-mono uppercase tracking-widest text-muted-foreground">Active Threats</CardTitle>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={dismissAllAlerts}
                        className="p-1 hover:bg-white/10 rounded transition-colors text-red-500/60 hover:text-red-400"
                        title="Dismiss All Threats"
                    >
                        <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <Badge variant="outline" className="text-[10px] font-mono border-red-500/20 text-red-400 bg-red-500/10">
                        {activeAlerts.length} DETECTED
                    </Badge>
                </div>
            </CardHeader>

            {/* Scrollable Content */}
            <CardContent className="flex-1 p-0 bg-muted/20 dark:bg-black/50 font-mono text-xs overflow-y-auto min-h-0 relative">
                {/* CRT Scanline Effect (dark mode only) */}
                <div className="absolute inset-0 pointer-events-none z-10 opacity-0 dark:opacity-5 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))]" style={{ backgroundSize: "100% 2px, 3px 100%" }} />

                <div className="space-y-2 p-2">
                    {activeAlerts.length === 0 ? (
                        <div className="text-muted-foreground italic p-6 text-center text-xs border border-dashed border-border dark:border-white/10 rounded">
                            <span>No active threats detected... scanning sector.</span>
                        </div>
                    ) : (
                        activeAlerts.map((alert) => {
                            const config = alertConfig[alert.type] || alertConfig.other;
                            const Icon = config.icon;
                            const isLife = alert.type === 'LIFE';

                            return (
                                <div
                                    key={alert.id}
                                    className={`
                                        relative group flex flex-col p-3 rounded-lg transition-all duration-300
                                        ${config.bg} border ${config.border}
                                        ${isLife ? 'animate-pulse-slow shadow-[0_0_15px_rgba(239,68,68,0.2)]' : ''}
                                    `}
                                >
                                    <div className="flex items-start justify-between mb-2">
                                        <div className="flex items-center space-x-2">
                                            <Icon className={`w-4 h-4 ${config.color}`} />
                                            <span className={`font-bold tracking-wider ${config.color}`}>
                                                {alert.type} DETECTED
                                            </span>
                                        </div>
                                        <span className="text-[10px] text-muted-foreground">
                                            {alert.timestamp}
                                        </span>
                                    </div>

                                    <div className="grid grid-cols-2 gap-2 text-foreground/70 dark:text-white/70 mb-3">
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">CONF:</span>
                                            <span className={`${alert.confidence > 0.8 ? 'text-green-400' : 'text-yellow-400'}`}>
                                                {(alert.confidence * 100).toFixed(0)}%
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">TEMP:</span>
                                            <span className={`${alert.max_temp > 38 ? 'text-red-400' : 'text-cyan-400'}`}>
                                                {alert.max_temp.toFixed(1)}°C
                                            </span>
                                        </div>
                                    </div>

                                    <div className="flex space-x-2">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="flex-1 h-7 text-[10px] border-border dark:border-white/10 hover:bg-accent/10 dark:hover:bg-white/10 bg-background/40 dark:bg-black/40"
                                            onClick={() => focusAlert(alert)}
                                        >
                                            <MapPin className="w-3 h-3 mr-1 text-cyan-400" />
                                            VIEW ON MAP
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-accent/10 dark:hover:bg-white/10"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                ackAlert(alert.id);
                                            }}
                                        >
                                            <X className="w-3 h-3" />
                                        </Button>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </CardContent>
        </Card>
    );
};
