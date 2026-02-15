import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
    Bluetooth, Signal, Target, Radar, SignalHigh, Cpu, SignalZero,
    Activity, Zap, Info, Shield, Gauge, Crosshair, MapPin, ChevronDown, ChevronUp, X
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

                setDevices(prev => {
                    const mergedMap = new Map<string, SignalDevice>();
                    prev.forEach(d => {
                        if (now - d.lastSeen < 12000) mergedMap.set(d.mac, d);
                    });
                    data.forEach((d: any) => {
                        mergedMap.set(d.mac, { ...d, lastSeen: now });
                    });
                    return Array.from(mergedMap.values()).sort((a, b) => b.rssi - a.rssi);
                });

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

    useEffect(() => {
        scan();
        const interval = setInterval(scan, 5000);
        return () => clearInterval(interval);
    }, [scan]);

    // --- Ultra-Smooth Metrics ---
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

    // Constant Smoothing Engine (Continuous Transition)
    useEffect(() => {
        if (!target) {
            setSmoothedRssi(null);
            return;
        }

        // Higher frequency update for "consistency" (30ms = 33Hz)
        const interval = setInterval(() => {
            const raw = target.rssi;
            setSmoothedRssi(prev => {
                const current = prev ?? raw;
                // Alpha 0.05 gives a fast but butter-smooth cinematic drift
                const next = current + (raw - current) * 0.05;
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

    return (
        <Card className="h-full bg-black/95 border-white/5 overflow-hidden flex flex-col shadow-2xl relative select-none">
            {/* HUD Header */}
            <CardHeader className="py-3 px-5 flex flex-row items-center justify-between space-y-0 border-b border-white/5 bg-zinc-950/90 z-20">
                <div className="flex items-center space-x-3">
                    <Activity className={`w-4 h-4 text-cyan-500 ${scanning ? 'animate-pulse' : ''}`} />
                    <CardTitle className="text-[11px] font-black uppercase tracking-[0.4em] text-white/70">SIGNAL TRACKER</CardTitle>
                </div>

                <div className="flex items-center space-x-3">
                    <Badge variant="outline" className={`h-4 text-[7px] border-white/10 px-2 transition-colors ${scanning ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20' : 'bg-white/5 text-white/20'}`}>
                        {scanning ? 'UPLINK_LIVE' : 'NET_IDLE'}
                    </Badge>
                </div>
            </CardHeader>

            <CardContent className="p-0 flex-1 flex flex-col overflow-hidden relative">
                {/* COLLAPSIBLE HUD SECTION */}
                <div
                    className={`transition-all duration-500 ease-in-out bg-zinc-950/40 relative overflow-hidden border-b border-white/5 ${target ? 'h-48' : 'h-0 opacity-0 border-none'}`}
                >
                    {/* Radar Pulse Background */}
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.1)_0,transparent_75%)] opacity-50" />
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(0,255,255,0.01)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,255,0.01)_1px,transparent_1px)] bg-[size:32px_32px]" />

                    <div className="absolute top-4 left-6 flex items-center space-x-2 px-2 py-0.5 bg-cyan-500/5 border border-cyan-500/20 rounded-sm">
                        <Target className="w-2.5 h-2.5 text-cyan-500" />
                        <span className="text-[8px] font-black text-cyan-500/60 uppercase tracking-widest">Target Engaged</span>
                    </div>

                    <button
                        onClick={() => setTarget(null)}
                        className="absolute top-4 right-6 p-1.5 rounded-full hover:bg-white/10 text-white/20 hover:text-white transition-all z-30"
                    >
                        <X className="w-3.5 h-3.5" />
                    </button>

                    {target && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center pt-2">
                            <div className="flex flex-col items-center animate-in fade-in zoom-in duration-500">
                                <div className={`text-6xl font-black font-mono tracking-tighter tabular-nums flex items-baseline leading-none transition-all duration-300 ${getSignalColor(smoothedRssi || target.rssi)}`}>
                                    {calculateDistance(smoothedRssi || target.rssi)}
                                    <span className="text-sm font-bold ml-1.5 text-white/30 uppercase tracking-[0.1em] italic">meters</span>
                                </div>
                                <div className="mt-4 flex items-center space-x-3 px-4 py-1 bg-white/5 border border-white/10 rounded-sm">
                                    <div className="text-[8px] font-mono text-cyan-400 uppercase tracking-tighter">{target.mac}</div>
                                    <div className="w-[1px] h-2.5 bg-white/10" />
                                    <div className="text-[8px] font-black text-white/40 uppercase tracking-widest">Quality: {getReliability(smoothedRssi || target.rssi)}%</div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* LIST SECTION - Always visible, scrolls below HUD */}
                <div className="flex-1 overflow-auto custom-scrollbar bg-black/60 pt-2 pb-4">
                    <div className="grid grid-cols-[1fr_60px_70px] px-6 py-2 text-[9px] font-black uppercase text-white/20 tracking-[0.25em] border-b border-white/5 sticky top-0 bg-black/95 z-20">
                        <span>Emitter_Identity</span>
                        <span className="text-center">Energy</span>
                        <span className="text-right">Distance</span>
                    </div>

                    <div className="px-3 py-1 space-y-1">
                        {devices.map((device) => (
                            <div
                                key={device.mac}
                                className={`group grid grid-cols-[1fr_60px_70px] items-center px-3 py-2.5 rounded-md transition-all duration-300 border ${target?.mac === device.mac ? 'bg-cyan-500/10 border-cyan-500/40 translate-x-1' : 'bg-transparent border-transparent hover:bg-white/[0.04] hover:translate-x-0.5'}`}
                                onClick={() => setTarget(device)}
                            >
                                <div className="flex items-center space-x-4">
                                    <div className={`p-2 rounded border transition-all ${target?.mac === device.mac ? 'border-cyan-500/50 text-cyan-400 bg-cyan-500/10' : 'border-white/5 text-white/20 bg-black/40'}`}>
                                        {device.type === 'wifi' ? <Signal className="w-3 h-3" /> : <Bluetooth className="w-3 h-3" />}
                                    </div>
                                    <div className="flex flex-col min-w-0">
                                        <div className="flex items-center space-x-2">
                                            <span className={`text-[11px] font-black transition-colors uppercase truncate ${target?.mac === device.mac ? 'text-white' : 'text-white/60 group-hover:text-white'}`}>
                                                {device.name || 'UNKNOWN_EMITTER'}
                                            </span>
                                            {scanning && <div className="w-1 h-1 rounded-full bg-cyan-500/30 animate-pulse" />}
                                        </div>
                                        <span className="text-[7px] font-mono text-white/20 uppercase tracking-widest">{device.mac}</span>
                                    </div>
                                </div>

                                <div className="flex flex-col items-center">
                                    <span className={`text-[10px] font-black tabular-nums transition-all ${getSignalColor(device.rssi)}`}>
                                        {device.rssi}
                                    </span>
                                    <div className="w-8 h-0.5 bg-white/5 rounded-full mt-1 overflow-hidden">
                                        <div className={`h-full ${getSignalColor(device.rssi).split(' ')[0].replace('text-', 'bg-')}`} style={{ width: `${Math.min(100, Math.max(0, (device.rssi + 95) * 1.8))}%` }} />
                                    </div>
                                </div>

                                <div className="text-right">
                                    <div className="text-[12px] font-black text-white/90 tabular-nums">
                                        {calculateDistance(device.rssi)}
                                        <span className="text-[8px] text-white/20 ml-0.5 font-bold italic uppercase tracking-tighter">m</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* DIAGNOSTIC FOOTER */}
                <div className="py-2.5 px-6 bg-zinc-950/90 border-t border-white/5 flex items-center justify-between">
                    <div className="flex items-center space-x-5 text-[7px] font-mono text-white/30 uppercase tracking-[0.2em]">
                        <div className="flex items-center space-x-1.5">
                            <Gauge className="w-2.5 h-2.5 text-cyan-500/40" />
                            <span>Calibration: Active</span>
                        </div>
                        <div className="flex items-center space-x-1.5">
                            <Shield className="w-2.5 h-2.5 text-emerald-500/40" />
                            <span>Persistence: {devices.length} IDs</span>
                        </div>
                    </div>
                    <div className="text-[8px] font-black text-white/10 uppercase tracking-[0.4em]">ST.V6_PRECISION</div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
