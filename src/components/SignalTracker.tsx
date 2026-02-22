import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
    Bluetooth, Signal, Target, Radar, Activity, Zap, Info, Shield, Gauge, X, MapPin, RefreshCw
} from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/badge';

interface SignalDevice {
    mac: string;
    name: string;
    rssi: number;
    type?: 'bluetooth' | 'wifi';
    lastSeen: number;
}

const SignalTracker = () => {
    const [devices, setDevices] = useState<SignalDevice[]>([]);
    const [scanning, setScanning] = useState(false);
    const [target, setTarget] = useState<SignalDevice | null>(null);
    const [smoothedRssi, setSmoothedRssi] = useState<number | null>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    const scan = useCallback(async () => {
        setScanning(true);
        try {
            const res = await apiFetch('/api/scan/bluetooth');
            if (res.ok) {
                const data = await res.json();
                const now = Date.now();

                setDevices(prev => {
                    const mergedMap = new Map<string, SignalDevice>();
                    // Aggressive Pruning: If not seen in the latest background scan, remove it.
                    // This creates a "Live" feel where lost devices drop off immediately.
                    data.forEach((d: any) => {
                        mergedMap.set(d.mac, { ...d, lastSeen: now });
                    });
                    return Array.from(mergedMap.values()).sort((a, b) => b.rssi - a.rssi);
                });

                if (target) {
                    const fresh = data.find((d: any) => d.mac === target.mac);
                    if (fresh) {
                        setTarget(prev => ({ ...prev!, rssi: fresh.rssi, lastSeen: now }));
                    } else if (now - (target.lastSeen || 0) > 12000) {
                        // If target lost for >12s, clear target
                        setTarget(null);
                    }
                }
            }
        } catch (e) {
            console.error(e);
        } finally {
            setScanning(false);
        }
    }, [target]);

    useEffect(() => {
        scan();
        // High-frequency polling (Instant Backend Cache retrieval)
        const interval = setInterval(scan, 2000);
        return () => clearInterval(interval);
    }, [scan]);

    // --- High-Resolution Smoother (33Hz) ---
    const calculateDistance = (rssi: number) => {
        const tx_ref = -56.5;
        const n = 2.25;
        const d = Math.pow(10, (tx_ref - rssi) / (10 * n));
        return d.toFixed(2);
    };

    const getReliability = (rssi: number) => {
        const score = Math.max(0, Math.min(100, (rssi + 95) * 1.6));
        return Math.round(score);
    };

    useEffect(() => {
        if (!target) {
            setSmoothedRssi(null);
            return;
        }

        const interval = setInterval(() => {
            const raw = target.rssi;
            setSmoothedRssi(prev => {
                const current = prev ?? raw;
                // Gain 0.15: Faster tracking for mobile targets, reduced lag
                const next = current + (raw - current) * 0.15;
                return Math.abs(next - current) < 0.001 ? raw : next;
            });
        }, 30);

        return () => clearInterval(interval);
    }, [target?.mac, target?.rssi]);

    const getSignalColor = (rssi: number) => {
        if (rssi > -60) return "text-cyan-400 drop-shadow-[0_0_15px_rgba(34,211,238,0.5)]";
        if (rssi > -72) return "text-emerald-400";
        if (rssi > -84) return "text-amber-500";
        return "text-rose-500";
    };

    // Auto-scroll to top when target is engaged to show HUD
    useEffect(() => {
        if (target && scrollContainerRef.current) {
            scrollContainerRef.current.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }, [target?.mac]);

    return (
        <Card className="h-full bg-white dark:bg-zinc-950/95 border-border dark:border-white/5 overflow-hidden flex flex-col shadow-2xl relative select-none font-sans">
            {/* Unified Scanline Overlay - Global to the box */}
            <div className="absolute inset-0 pointer-events-none opacity-[0.02] bg-[linear-gradient(transparent_50%,rgba(0,0,0,0.5)_50%),linear-gradient(90deg,rgba(0,255,255,0.05)_1px,transparent_1px)] bg-[size:100%_2px,32px_100%] z-50" />

            <CardHeader className="py-3 px-5 flex flex-row items-center justify-between space-y-0 border-b border-border dark:border-white/5 bg-muted/50 dark:bg-black/40 backdrop-blur-md z-40">
                <div className="flex items-center space-x-3">
                    <Activity className={`w-4 h-4 text-cyan-600 dark:text-cyan-500 ${scanning ? 'animate-pulse' : ''}`} />
                    <CardTitle className="text-[11px] font-black uppercase tracking-[0.45em] text-foreground/60 dark:text-white/60">SIGNAL TRACKER</CardTitle>
                </div>
                <div className="flex items-center space-x-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-muted-foreground hover:text-cyan-600 dark:text-white/40 dark:hover:text-cyan-400 hover:bg-cyan-500/10"
                        onClick={scan}
                        disabled={scanning}
                    >
                        <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} />
                    </Button>
                    <Badge variant="outline" className={`h-4 text-[7px] border-border dark:border-white/10 px-2 flex items-center space-x-1.5 ${scanning ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400' : 'bg-muted dark:bg-white/5 text-muted-foreground dark:text-white/20'}`}>
                        <div className={`w-1 h-1 rounded-full ${scanning ? 'bg-cyan-500 animate-pulse' : 'bg-muted-foreground dark:bg-white/20'}`} />
                        <span>{scanning ? 'UPLINK_LIVE' : 'NET_IDLE'}</span>
                    </Badge>
                </div>
            </CardHeader>

            {/* UNIFIED SCROLLABLE BOX */}
            <CardContent
                ref={scrollContainerRef}
                className="p-0 flex-1 overflow-auto custom-scrollbar relative z-10 scroll-smooth bg-transparent dark:bg-black/5"
            >
                {/* HUD Section - Integrated at the top of scroll flow */}
                <div
                    className={`transition-all duration-700 ease-out relative overflow-hidden bg-gradient-to-b from-cyan-500/[0.03] to-transparent ${target ? 'h-52 opacity-100' : 'h-0 opacity-0'}`}
                >
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.06)_0,transparent_75%)]" />

                    <div className="absolute top-4 left-6 flex items-center space-x-2 px-2 py-0.5 bg-cyan-500/5 rounded border border-cyan-500/20 z-20">
                        <Target className="w-2.5 h-2.5 text-cyan-600 dark:text-cyan-500" />
                        <span className="text-[8px] font-black text-foreground/40 dark:text-white/40 uppercase tracking-widest">Target Engaged</span>
                    </div>

                    <button
                        onClick={() => setTarget(null)}
                        className="absolute top-4 right-6 p-1.5 rounded-full hover:bg-accent dark:hover:bg-white/10 text-muted-foreground dark:text-white/10 hover:text-foreground dark:hover:text-white transition-all z-40"
                    >
                        <X className="w-3.5 h-3.5" />
                    </button>

                    {target && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center pt-4">
                            <div className="flex flex-col items-center animate-in fade-in zoom-in-95 duration-500">
                                <div className={`text-6xl font-black font-mono tracking-tighter tabular-nums flex items-baseline leading-none drop-shadow-[0_0_20px_rgba(34,211,238,0.2)] ${getSignalColor(smoothedRssi || target.rssi)}`}>
                                    {calculateDistance(smoothedRssi || target.rssi)}
                                    <span className="text-sm font-bold ml-1.5 text-muted-foreground dark:text-white/20 uppercase tracking-[0.1em] italic">meters</span>
                                </div>
                                <div className="mt-4 flex items-center space-x-3 px-4 py-1.5 bg-white/50 dark:bg-black/40 border border-border dark:border-white/5 rounded backdrop-blur-xl">
                                    <div className="text-[8px] font-mono text-cyan-600 dark:text-cyan-500/80 uppercase tracking-tighter tabular-nums">{target.mac}</div>
                                    <div className="w-[1px] h-3 bg-border dark:bg-white/10" />
                                    <div className="text-[8px] font-black text-foreground/40 dark:text-white/40 uppercase tracking-widest">SNR: {getReliability(smoothedRssi || target.rssi)}%</div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* LIST SECTION - 2 COLUMN SIMPLIFIED */}
                <div className="min-h-full">
                    <div className="grid grid-cols-[1fr_80px] px-6 py-3 text-[9px] font-black uppercase text-foreground/40 dark:text-white/20 tracking-[0.3em] border-b border-border dark:border-white/5 sticky top-0 bg-background/90 dark:bg-zinc-950/90 backdrop-blur-xl z-30">
                        <span>Identity</span>
                        <span className="text-right">Distance</span>
                    </div>

                    <div className="px-3 py-2 space-y-0.5 pb-8">
                        {devices.map((device) => (
                            <div
                                key={device.mac}
                                className={`group grid grid-cols-[1fr_80px] items-center px-4 py-3 rounded transition-all duration-300 ${target?.mac === device.mac ? 'bg-cyan-500/10 shadow-[0_0_20px_rgba(6,182,212,0.05)] border border-cyan-500/10' : 'bg-transparent border border-transparent hover:bg-black/[0.03] dark:hover:bg-white/[0.03]'}`}
                                onClick={() => setTarget(device)}
                            >
                                <div className="flex items-center space-x-4">
                                    <div className={`p-2 rounded border transition-all duration-300 ${target?.mac === device.mac ? 'border-cyan-500/50 text-cyan-600 dark:text-cyan-400 bg-cyan-500/10' : 'border-border dark:border-white/5 text-muted-foreground dark:text-white/20 bg-muted/50 dark:bg-black/20'}`}>
                                        {device.type === 'wifi' ? <Signal className="w-3 h-3" /> : <Bluetooth className="w-3 h-3" />}
                                    </div>
                                    <div className="flex flex-col min-w-0">
                                        <div className="flex items-center space-x-2">
                                            <span className={`text-[12px] font-bold transition-colors truncate uppercase ${target?.mac === device.mac ? 'text-foreground dark:text-white' : 'text-foreground/50 dark:text-white/50 group-hover:text-foreground/80 dark:group-hover:text-white/80'}`}>
                                                {device.name || 'ANON_OBJECT'}
                                            </span>
                                        </div>
                                        <span className="text-[7px] font-mono text-muted-foreground/50 dark:text-white/15 uppercase tracking-widest leading-none mt-0.5">{device.mac}</span>
                                    </div>
                                </div>

                                <div className="text-right">
                                    <div className={`text-[13px] font-black transition-all tabular-nums ${target?.mac === device.mac ? 'text-cyan-600 dark:text-cyan-400' : 'text-foreground/80 dark:text-white/80'}`}>
                                        {calculateDistance(device.rssi)}
                                        <span className="text-[8px] text-muted-foreground dark:text-white/20 ml-0.5 font-bold italic lowercase">m</span>
                                    </div>
                                </div>
                            </div>
                        ))}

                        {devices.length === 0 && !scanning && (
                            <div className="py-20 text-center opacity-20">
                                <Radar className="w-10 h-10 mx-auto mb-2" />
                            </div>
                        )}
                    </div>
                </div>
            </CardContent>

            {/* INTEGRATED FOOTER */}
            <div className="py-2.5 px-6 bg-muted/20 dark:bg-zinc-950 border-t border-border dark:border-white/5 flex items-center justify-between text-[7px] font-mono text-muted-foreground dark:text-white/20 uppercase tracking-[0.3em] z-40">
                <div className="flex items-center space-x-5">
                    <div className="flex items-center space-x-1.5">
                        <Gauge className="w-2.5 h-2.5 text-cyan-600/30 dark:text-cyan-500/30" />
                        <span>Adaptive_Ref: -56.5</span>
                    </div>
                    <div className="flex items-center space-x-1.5">
                        <Shield className="w-2.5 h-2.5 text-emerald-600/30 dark:text-emerald-500/30" />
                        <span>Precision_Lock: Ready</span>
                    </div>
                </div>
                <div className="text-foreground/30 dark:text-white/10 font-black">ST.V7_UNIFIED</div>
            </div>
        </Card>
    );
};

export default SignalTracker;
