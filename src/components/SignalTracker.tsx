import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
    Bluetooth, Signal, Target, Radar, Activity, Zap, Info, Shield, Gauge, X, MapPin
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
                // Alpha 0.05: Fast response, but cinematic fluidity
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
        <Card className="h-full bg-zinc-950/90 border-white/5 overflow-hidden flex flex-col shadow-2xl relative select-none group font-sans">
            {/* Unified Scanline Overlay */}
            <div className="absolute inset-0 pointer-events-none opacity-[0.02] bg-[linear-gradient(transparent_50%,rgba(0,0,0,0.5)_50%),linear-gradient(90deg,rgba(0,255,255,0.05)_1px,transparent_1px)] bg-[size:100%_2px,32px_100%]" />

            <CardHeader className="py-3 px-5 flex flex-row items-center justify-between space-y-0 border-b border-white/5 bg-black/40 backdrop-blur-md z-30">
                <div className="flex items-center space-x-3">
                    <Activity className={`w-4 h-4 text-cyan-500 ${scanning ? 'animate-pulse' : ''}`} />
                    <CardTitle className="text-[11px] font-black uppercase tracking-[0.45em] text-white/60">SIGNAL TRACKER</CardTitle>
                </div>
                <div className="flex items-center space-x-2">
                    <Badge variant="outline" className={`h-4 text-[7px] border-white/10 px-2 flex items-center space-x-1.5 ${scanning ? 'bg-cyan-500/10 text-cyan-400' : 'bg-white/5 text-white/20'}`}>
                        <div className={`w-1 h-1 rounded-full ${scanning ? 'bg-cyan-500 animate-pulse' : 'bg-white/20'}`} />
                        <span>{scanning ? 'UPLINK_LIVE' : 'NET_IDLE'}</span>
                    </Badge>
                </div>
            </CardHeader>

            <CardContent className="p-0 flex-1 flex flex-col overflow-hidden relative z-10">
                {/* ONE UNIFIED BOX - Collapsible HUD Integrated Seamleassly */}
                <div
                    className={`transition-all duration-700 ease-out relative overflow-hidden bg-black/20 ${target ? 'h-48' : 'h-0 opacity-0'}`}
                >
                    {/* Integrated HUD UI (No internal dividers) */}
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.08)_0,transparent_75%)]" />

                    <div className="absolute top-4 left-6 flex items-center space-x-2 px-2 py-0.5 bg-cyan-500/5 rounded border border-cyan-500/20">
                        <Target className="w-2.5 h-2.5 text-cyan-500" />
                        <span className="text-[8px] font-black text-white/30 uppercase tracking-widest">Target Engaged</span>
                    </div>

                    <button
                        onClick={() => setTarget(null)}
                        className="absolute top-4 right-6 p-1.5 rounded-full hover:bg-white/10 text-white/10 hover:text-white transition-all z-40"
                    >
                        <X className="w-3.5 h-3.5" />
                    </button>

                    {target && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center pt-2">
                            <div className="flex flex-col items-center animate-in fade-in zoom-in-95 duration-500">
                                <div className={`text-6xl font-black font-mono tracking-tighter tabular-nums flex items-baseline leading-none drop-shadow-[0_0_20px_rgba(34,211,238,0.2)] ${getSignalColor(smoothedRssi || target.rssi)}`}>
                                    {calculateDistance(smoothedRssi || target.rssi)}
                                    <span className="text-sm font-bold ml-1.5 text-white/20 uppercase tracking-[0.1em] italic">meters</span>
                                </div>
                                <div className="mt-4 flex items-center space-x-3 px-4 py-1.5 bg-black/40 border border-white/5 rounded backdrop-blur-xl">
                                    <div className="text-[8px] font-mono text-cyan-500/80 uppercase tracking-tighter tabular-nums">{target.mac}</div>
                                    <div className="w-[1px] h-3 bg-white/10" />
                                    <div className="text-[8px] font-black text-white/40 uppercase tracking-widest">SNR: {getReliability(smoothedRssi || target.rssi)}%</div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* LIST SECTION - Seamleassly joined to above */}
                <div className="flex-1 overflow-auto custom-scrollbar bg-black/10">
                    <div className="grid grid-cols-[1fr_60px_70px] px-6 py-3 text-[9px] font-black uppercase text-white/15 tracking-[0.3em] border-b border-white/5 sticky top-0 bg-zinc-950/80 backdrop-blur-xl z-20">
                        <span>Identity</span>
                        <span className="text-center">Energy</span>
                        <span className="text-right">Distance</span>
                    </div>

                    <div className="px-3 py-1.5 space-y-0.5">
                        {devices.map((device) => (
                            <div
                                key={device.mac}
                                className={`group grid grid-cols-[1fr_60px_70px] items-center px-3 py-2.5 rounded transition-all duration-300 ${target?.mac === device.mac ? 'bg-cyan-500/10 shadow-[0_0_20px_rgba(6,182,212,0.05)]' : 'bg-transparent hover:bg-white/[0.03]'}`}
                                onClick={() => setTarget(device)}
                            >
                                <div className="flex items-center space-x-4">
                                    <div className={`p-2 rounded border transition-all duration-300 ${target?.mac === device.mac ? 'border-cyan-500/50 text-cyan-400 bg-cyan-500/10' : 'border-white/5 text-white/20 bg-black/20'}`}>
                                        {device.type === 'wifi' ? <Signal className="w-3 h-3" /> : <Bluetooth className="w-3 h-3" />}
                                    </div>
                                    <div className="flex flex-col min-w-0">
                                        <div className="flex items-center space-x-2">
                                            <span className={`text-[12px] font-bold transition-colors truncate uppercase ${target?.mac === device.mac ? 'text-white' : 'text-white/50 group-hover:text-white/80'}`}>
                                                {device.name || 'ANON_OBJECT'}
                                            </span>
                                        </div>
                                        <span className="text-[7px] font-mono text-white/15 uppercase tracking-widest leading-none mt-0.5">{device.mac}</span>
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
                                    <div className="text-[12px] font-black text-white/80 tabular-nums">
                                        {calculateDistance(device.rssi)}
                                        <span className="text-[8px] text-white/20 ml-0.5 font-bold italic lowercase">m</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* FOOTER - INTEGRATED */}
                <div className="py-2.5 px-6 bg-black/40 border-t border-white/5 flex items-center justify-between text-[7px] font-mono text-white/20 uppercase tracking-[0.3em]">
                    <div className="flex items-center space-x-5">
                        <div className="flex items-center space-x-1.5">
                            <Gauge className="w-2.5 h-2.5 text-cyan-500/30" />
                            <span>Adaptive_Ref: -56.5</span>
                        </div>
                        <div className="flex items-center space-x-1.5">
                            <Shield className="w-2.5 h-2.5 text-emerald-500/30" />
                            <span>Precision_Lock: Ready</span>
                        </div>
                    </div>
                    <div className="text-white/10 font-black">ST.V6_CORE</div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
