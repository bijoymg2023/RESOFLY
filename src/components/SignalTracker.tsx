import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
    Bluetooth, Signal, Target, Radar, SignalHigh, Cpu, SignalZero,
    Activity, Zap, Info, Shield, Gauge, Crosshair, MapPin
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

    const scan = useCallback(async () => {
        setScanning(true);
        try {
            const res = await apiFetch('/api/scan/bluetooth');
            if (res.ok) {
                const data = await res.json();
                const now = Date.now();

                // PERSISTENT MERGE LOGIC:
                // We merge new data with existing list to prevent "disappearing" flicker.
                // We keep "inactive" devices for 15 seconds before removal.
                setDevices(prev => {
                    const mergedMap = new Map<string, SignalDevice>();

                    // 1. Add current devices (to be updated)
                    prev.forEach(d => {
                        if (now - d.lastSeen < 15000) mergedMap.set(d.mac, d);
                    });

                    // 2. Override with fresh scan data
                    data.forEach((d: any) => {
                        mergedMap.set(d.mac, { ...d, lastSeen: now });
                    });

                    return Array.from(mergedMap.values()).sort((a, b) => b.rssi - a.rssi);
                });

                // Update target reference silently
                if (target) {
                    const fresh = data.find((d: any) => d.mac === target.mac);
                    if (fresh) {
                        setTarget(prev => ({ ...prev!, rssi: fresh.rssi, lastSeen: now }));
                    }
                }
            }
        } catch (e) {
            console.error(e);
        } finally {
            setScanning(false);
        }
    }, [target?.mac]);

    // 5-Second Refresh Cycle
    useEffect(() => {
        scan();
        const interval = setInterval(scan, 5000);
        return () => clearInterval(interval);
    }, [scan]);

    // --- High-Precision Distance Math ---
    const calculateDistance = (rssi: number) => {
        // Sigma-Optimized Indoor Path Loss Model
        // tx_ref: -56.5 (Standardized for high-gain antenna/Pi calibration)
        // n: 2.25 (Average residential/office density)
        const tx_ref = -56.5;
        const n = 2.25;
        const d = Math.pow(10, (tx_ref - rssi) / (10 * n));

        // Centimeter Precision (2 decimals)
        return d.toFixed(2);
    };

    const getReliability = (rssi: number) => {
        const score = Math.max(0, Math.min(100, (rssi + 95) * 1.6));
        return Math.round(score);
    };

    // Ultra-Smooth EMA Filter (20Hz)
    useEffect(() => {
        if (!target) {
            setSmoothedRssi(null);
            return;
        }

        const interval = setInterval(() => {
            const raw = target.rssi;
            setSmoothedRssi(prev => {
                const current = prev ?? raw;
                // Alpha 0.04: Extremely stable, no jitter, cinematic transition
                const next = current + (raw - current) * 0.04;
                return next;
            });
        }, 50);

        return () => clearInterval(interval);
    }, [target?.mac, target?.rssi]);

    const getSignalColor = (rssi: number) => {
        if (rssi > -60) return "text-cyan-400 drop-shadow-[0_0_15px_rgba(34,211,238,0.5)]";
        if (rssi > -72) return "text-emerald-400";
        if (rssi > -84) return "text-amber-500";
        return "text-rose-500";
    };

    return (
        <Card className="h-full bg-black/95 border-white/5 overflow-hidden flex flex-col shadow-2xl relative font-sans select-none">
            {/* HUD Scanline Overlay */}
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[linear-gradient(transparent_50%,rgba(0,0,0,0.5)_50%),linear-gradient(90deg,rgba(0,255,255,0.1)_1px,transparent_1px)] bg-[size:100%_2px,24px_100%] z-50" />

            <CardHeader className="py-2.5 px-4 flex flex-row items-center justify-between space-y-0 border-b border-white/5 bg-zinc-950/80 backdrop-blur-md">
                <div className="flex items-center space-x-3">
                    <div className="relative">
                        <Radar className={`w-3.5 h-3.5 text-cyan-500 ${scanning ? 'animate-pulse' : ''}`} />
                        {scanning && <div className="absolute -inset-1 bg-cyan-500/20 rounded-full animate-ping" />}
                    </div>
                    <CardTitle className="text-[10px] font-black uppercase tracking-[0.35em] text-white/40">SigIntel Matrix</CardTitle>
                </div>

                <div className="flex items-center space-x-2">
                    <div className="text-[8px] font-mono text-cyan-500/30 uppercase tracking-[0.1em] hidden sm:block">
                        Refresh: 5s
                    </div>
                    <Badge variant="outline" className={`h-4 text-[7px] border-white/10 px-2 flex items-center space-x-1.5 ${scanning ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20' : 'bg-white/5 text-white/20'}`}>
                        <div className={`w-1 h-1 rounded-full ${scanning ? 'bg-cyan-500 animate-pulse' : 'bg-white/20'}`} />
                        <span>{scanning ? 'UPLINK_LIVE' : 'NET_IDLE'}</span>
                    </Badge>
                </div>
            </CardHeader>

            <CardContent className="p-0 flex-1 flex flex-col overflow-hidden relative">
                {/* Visualizer Area - Redesigned to fit tightly */}
                <div className="h-44 bg-zinc-950/40 flex items-center justify-center relative overflow-hidden border-b border-white/5 group">
                    {/* Concentric Grid Rings */}
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.1)_0,transparent_75%)]" />
                    <div className="absolute w-[280px] h-[280px] rounded-full border border-white/[0.02]" />
                    <div className="absolute w-[180px] h-[180px] rounded-full border border-cyan-500/5" />
                    <div className="absolute w-[100px] h-[100px] rounded-full border border-cyan-500/10 flex items-center justify-center">
                        <div className="w-1 h-24 bg-gradient-to-t from-transparent via-cyan-500/30 to-transparent animate-[spin_6s_linear_infinite]" />
                    </div>

                    {target ? (
                        <div className="relative z-10 w-full flex flex-col items-center justify-center px-6 animate-in fade-in duration-500">
                            {/* HUD Decor Lines */}
                            <div className="absolute top-2 left-6 right-6 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent" />

                            <div className="flex items-center space-x-2 mb-2">
                                <Shield className="w-2.5 h-2.5 text-cyan-500/50" />
                                <span className="text-[8px] font-black text-cyan-500/40 uppercase tracking-[0.3em]">Precision Target Lock</span>
                            </div>

                            {/* Centimeter Precision Display */}
                            <div className="flex flex-col items-center justify-center">
                                <div className={`text-6xl font-black font-mono tracking-tighter tabular-nums flex items-baseline leading-none drop-shadow-[0_0_25px_rgba(34,211,238,0.15)] ${getSignalColor(smoothedRssi || -100)}`}>
                                    {calculateDistance(smoothedRssi || target.rssi)}
                                    <span className="text-xs font-bold ml-1.5 text-white/30 uppercase tracking-[0.1em] italic select-none">meters</span>
                                </div>

                                <div className="mt-4 flex items-center space-x-3 bg-black/60 border border-white/5 px-2.5 py-1 rounded-sm backdrop-blur-md">
                                    <div className="flex items-center space-x-1.5 text-[8px] font-mono text-cyan-400">
                                        <MapPin className="w-2.5 h-2.5" />
                                        <span>{target.mac}</span>
                                    </div>
                                    <div className="w-[1px] h-2 bg-white/10" />
                                    <div className="text-[8px] font-black text-white/40 uppercase tracking-widest">
                                        Quality: {getReliability(smoothedRssi || target.rssi)}%
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="relative z-10 text-center flex flex-col items-center opacity-40">
                            <div className="relative w-16 h-16 flex items-center justify-center mb-4">
                                <div className="absolute inset-0 border border-white/10 rounded-full animate-pulse" />
                                <SignalZero className="w-6 h-6 text-white/60" />
                            </div>
                            <div className="text-[9px] font-black uppercase tracking-[0.5em] text-white/40">Searching for Emitters</div>
                        </div>
                    )}
                </div>

                {/* Signals Table - Streamlined & Persistent */}
                <div className="flex-1 overflow-auto custom-scrollbar bg-black/40">
                    <div className="grid grid-cols-[1fr_60px_70px] px-5 py-2 text-[8px] font-black uppercase text-white/20 tracking-[0.2em] border-b border-white/5 sticky top-0 bg-zinc-950/95 z-20">
                        <span>Emitter_Identity</span>
                        <span className="text-center">Energy</span>
                        <span className="text-right">Distance</span>
                    </div>

                    <div className="py-1 px-2 space-y-0.5">
                        {devices.map((device, i) => (
                            <div
                                key={device.mac}
                                className={`group grid grid-cols-[1fr_60px_70px] items-center px-3 py-2 rounded-md transition-all duration-300 border ${target?.mac === device.mac ? 'bg-cyan-500/10 border-cyan-500/40 shadow-[0_0_15px_rgba(6,182,212,0.1)]' : 'bg-transparent border-transparent hover:bg-white/[0.04]'}`}
                                onClick={() => setTarget(device)}
                            >
                                <div className="flex items-center space-x-3 overflow-hidden">
                                    <div className={`p-1.5 rounded-sm border ${target?.mac === device.mac ? 'border-cyan-500/50 text-cyan-400' : 'border-white/5 text-white/20'} transition-colors`}>
                                        {device.type === 'wifi' ? <Signal className="w-3 h-3" /> : <Bluetooth className="w-3 h-3" />}
                                    </div>
                                    <div className="flex flex-col min-w-0">
                                        <div className="flex items-center space-x-2">
                                            <span className={`text-[11px] font-bold transition-colors truncate ${target?.mac === device.mac ? 'text-white' : 'text-white/60 group-hover:text-white/90'}`}>
                                                {device.name || 'UNKNOWN_EMITTER'}
                                            </span>
                                            {scanning && <div className="w-1 h-1 rounded-full bg-cyan-500/40 animate-pulse" />}
                                        </div>
                                        <span className="text-[7px] font-mono text-white/10 uppercase tracking-tighter">{device.mac}</span>
                                    </div>
                                </div>

                                <div className="flex flex-col items-center">
                                    <span className={`text-[10px] font-black tabular-nums transition-all ${getSignalColor(device.rssi)}`}>
                                        {device.rssi}
                                    </span>
                                    <div className="w-8 h-0.5 bg-white/5 rounded-full mt-1 overflow-hidden opacity-50">
                                        <div className={`h-full ${getSignalColor(device.rssi).split(' ')[0].replace('text-', 'bg-')}`} style={{ width: `${Math.min(100, Math.max(0, (device.rssi + 95) * 1.8))}%` }} />
                                    </div>
                                </div>

                                <div className="text-right">
                                    <div className="text-[11px] font-black text-white tabular-nums flex items-baseline justify-end transition-all">
                                        {calculateDistance(device.rssi)}
                                        <span className="text-[8px] text-white/30 ml-0.5 uppercase tracking-tighter italic">m</span>
                                    </div>
                                </div>
                            </div>
                        ))}

                        {devices.length === 0 && !scanning && (
                            <div className="py-16 text-center opacity-20">
                                <Radar className="w-10 h-10 mx-auto mb-2" />
                                <div className="text-[9px] font-black uppercase tracking-widest">No Intelligence Collected</div>
                            </div>
                        )}
                    </div>
                </div>

                {/* HUD Footer Status */}
                <div className="py-2 px-4 bg-zinc-950/90 border-t border-white/5 flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                        <div className="flex items-center space-x-1.5 text-[7px] font-black text-white/20 uppercase tracking-widest">
                            <Gauge className="w-2.5 h-2.5 text-cyan-500/40" />
                            <span>Precision_Ref: -56.5dB</span>
                        </div>
                        <div className="flex items-center space-x-1.5 text-[7px] font-black text-emerald-500/40 uppercase tracking-widest">
                            <Shield className="w-2.5 h-2.5" />
                            <span>Signal_Merge: Active</span>
                        </div>
                    </div>
                    <div className="text-[8px] font-black text-white/10 tracking-[0.2em]">SIGINT MK-V PROTOCOL</div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
