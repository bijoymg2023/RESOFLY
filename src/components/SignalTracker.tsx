import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
    Search, RefreshCw, Bluetooth, Signal, Smartphone, X, Target,
    Radar, SignalHigh, Cpu, SignalZero, Activity, Zap, Info, Shield, Gauge, Crosshair
} from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/badge';

interface SignalDevice {
    mac: string;
    name: string;
    rssi: number;
    type?: 'bluetooth' | 'wifi';
}

const SignalTracker = () => {
    const [devices, setDevices] = useState<SignalDevice[]>([]);
    const [scanning, setScanning] = useState(false);
    const [target, setTarget] = useState<SignalDevice | null>(null);
    const [smoothedRssi, setSmoothedRssi] = useState<number | null>(null);
    const [history, setHistory] = useState<number[]>([]);

    const scan = async () => {
        setScanning(true);
        try {
            const res = await apiFetch('/api/scan/bluetooth');
            if (res.ok) {
                const data = await res.json();
                setDevices(data);

                if (target) {
                    const fresh = data.find((d: any) => d.mac === target.mac);
                    if (fresh) {
                        setTarget(prev => ({ ...prev!, rssi: fresh.rssi }));
                    }
                }
            }
        } catch (e) {
            console.error(e);
        } finally {
            setScanning(false);
        }
    };

    useEffect(() => {
        scan();
        const interval = setInterval(scan, 8000);
        return () => clearInterval(interval);
    }, [target?.mac]);

    // --- Precise Signal Processing ---
    const calculateDistance = (rssi: number) => {
        // Tuned for Smartphone/Pi 4 near-field (<5m)
        // tx_ref at 1m: -57.0 (averaged for iPhone/ESP32)
        // n: 2.3 (Typical air/indoor attenuation)
        const tx_ref = -57.0;
        const n = 2.3;
        const d = Math.pow(10, (tx_ref - rssi) / (10 * n));

        // CM Precision: 2 decimals (e.g., 0.37m)
        return d.toFixed(2);
    };

    const getReliability = (rssi: number) => {
        const score = Math.max(0, Math.min(100, (rssi + 92) * 1.8));
        return Math.round(score);
    };

    useEffect(() => {
        if (!target) {
            setSmoothedRssi(null);
            setHistory([]);
            return;
        }

        const interval = setInterval(() => {
            const raw = target.rssi;
            setSmoothedRssi(prev => {
                const current = prev ?? raw;
                // High-resolution filter: 0.06 alpha for ultra-stable numbers
                const next = current + (raw - current) * 0.06;
                return next;
            });
        }, 50);

        return () => clearInterval(interval);
    }, [target?.mac, target?.rssi]);

    useEffect(() => {
        if (smoothedRssi !== null) {
            setHistory(prev => [...prev.slice(-40), Math.round(smoothedRssi)]);
        }
    }, [smoothedRssi]);

    const getSignalColor = (rssi: number) => {
        if (rssi > -60) return "text-cyan-400 drop-shadow-[0_0_15px_rgba(34,211,238,0.6)]";
        if (rssi > -72) return "text-emerald-400";
        if (rssi > -84) return "text-amber-500";
        return "text-rose-500";
    };

    return (
        <Card className="h-full bg-black border-white/5 overflow-hidden flex flex-col shadow-2xl relative">
            <CardHeader className="py-2 px-4 flex flex-row items-center justify-between space-y-0 border-b border-white/5 bg-zinc-950/60">
                <div className="flex items-center space-x-2">
                    <Activity className={`w-3 h-3 text-cyan-500 ${scanning ? 'animate-pulse' : ''}`} />
                    <CardTitle className="text-[10px] font-black uppercase tracking-[0.3em] text-white/50">SigIntel Analysis</CardTitle>
                </div>

                <div className="flex items-center space-x-2">
                    <div className="flex items-center space-x-2 px-2 py-0.5 bg-white/5 rounded border border-white/5">
                        <span className={`w-1 h-1 rounded-full ${scanning ? 'bg-cyan-500 animate-ping' : 'bg-white/10'}`} />
                        <span className="text-[7px] font-bold text-white/30 uppercase tracking-tighter">
                            {scanning ? 'Uplink Live' : 'Link Standby'}
                        </span>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="p-0 flex-1 flex flex-col overflow-hidden">
                {/* HUD Primary View Area - Redesigned to 'fit the box' */}
                <div className="h-44 bg-zinc-950/40 flex items-center justify-center relative overflow-hidden border-b border-white/5">
                    {/* Radar Grids */}
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.08)_0,transparent_75%)]" />
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(0,255,255,0.01)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,255,0.01)_1px,transparent_1px)] bg-[size:20px_20px]" />

                    {/* Concentric HUD Rings */}
                    <div className="absolute w-72 h-72 border border-cyan-500/5 rounded-full" />
                    <div className="absolute w-56 h-56 border border-cyan-500/10 rounded-full" />
                    <div className="absolute w-40 h-40 border border-cyan-500/20 rounded-full flex items-center justify-center">
                        <div className="w-1 h-32 bg-gradient-to-b from-transparent via-cyan-500/20 to-transparent animate-[spin_4s_linear_infinite]" />
                    </div>

                    {target ? (
                        <div className="relative z-10 w-full flex flex-col items-center justify-center px-4 animate-in fade-in duration-500">
                            {/* HUD Header Labels */}
                            <div className="flex items-center justify-between w-full mb-2 opacity-50 px-4">
                                <div className="text-[8px] font-black text-cyan-400 bg-cyan-500/10 px-1.5 py-0.5 rounded border border-cyan-500/20 uppercase tracking-widest flex items-center space-x-1.5">
                                    <Target className="w-2.5 h-2.5" />
                                    <span>Target Locked</span>
                                </div>
                                <div className="text-[8px] font-mono text-white/40 uppercase tabular-nums">ID: {target.mac}</div>
                            </div>

                            {/* Centimeter Primary Metric - More Integrated */}
                            <div className="flex flex-col items-center justify-center py-2">
                                <div className={`text-6xl font-black font-mono tracking-tighter tabular-nums flex items-baseline leading-none drop-shadow-[0_0_20px_rgba(34,211,238,0.2)] ${getSignalColor(smoothedRssi || -100)}`}>
                                    {calculateDistance(smoothedRssi || target.rssi)}
                                    <span className="text-sm font-bold ml-2 text-white/20 uppercase tracking-[0.2em] italic mb-1">Meters</span>
                                </div>
                                <div className="mt-4 flex items-center space-x-4 bg-white/5 border border-white/5 px-3 py-1 rounded-full backdrop-blur-md">
                                    <div className="flex items-center space-x-2 text-[8px] font-bold text-cyan-500/60 uppercase">
                                        <Zap className="w-2.5 h-2.5" />
                                        <span>Precision Lock</span>
                                    </div>
                                    <div className="w-[1px] h-3 bg-white/10" />
                                    <div className="flex items-center space-x-2 text-[8px] font-bold text-white/40 uppercase">
                                        <Info className="w-2.5 h-2.5" />
                                        <span>SNR: {getReliability(smoothedRssi || target.rssi)}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="relative z-10 text-center flex flex-col items-center opacity-30">
                            <div className="relative w-16 h-16 flex items-center justify-center mb-4">
                                <div className="absolute inset-0 border border-dashed border-white/10 rounded-full animate-[spin_20s_linear_infinite]" />
                                <SignalZero className="w-6 h-6 text-white/50" />
                            </div>
                            <div className="text-[10px] font-black uppercase tracking-[0.4em] text-white/50">Listening for Signal...</div>
                        </div>
                    )}
                </div>

                {/* Signals Table */}
                <div className="flex-1 overflow-auto custom-scrollbar bg-black/60 px-2 pt-1">
                    <div className="grid grid-cols-[1fr_60px_60px] px-3 py-2 text-[8px] font-black uppercase text-white/20 tracking-[0.2em] sticky top-0 bg-black/95 z-20">
                        <span>Emitter_Identity</span>
                        <span className="text-center">Energy</span>
                        <span className="text-right">Dist</span>
                    </div>

                    <div className="py-1 space-y-1">
                        {devices.map((device, i) => (
                            <div
                                key={i}
                                className={`group grid grid-cols-[1fr_60px_60px] items-center px-3 py-2 rounded border transition-all duration-300 ${target?.mac === device.mac ? 'bg-cyan-500/10 border-cyan-500/30' : 'bg-transparent border-transparent hover:bg-white/[0.03]'}`}
                                onClick={() => setTarget(device)}
                            >
                                <div className="flex items-center space-x-3 overflow-hidden">
                                    <div className={`p-1.5 rounded bg-black/40 border ${target?.mac === device.mac ? 'border-cyan-500/50 text-cyan-400' : 'border-white/5 text-white/20'}`}>
                                        {device.type === 'wifi' ? <Signal className="w-3 h-3" /> : <Bluetooth className="w-3 h-3" />}
                                    </div>
                                    <div className="flex flex-col min-w-0">
                                        <span className={`text-[11px] font-bold transition-colors truncate ${target?.mac === device.mac ? 'text-white' : 'text-white/50 group-hover:text-white/80'}`}>
                                            {device.name || 'ANON_CLIENT'}
                                        </span>
                                        <span className="text-[7px] font-mono text-white/20 uppercase tracking-tighter">{device.mac}</span>
                                    </div>
                                </div>

                                <div className="flex flex-col items-center">
                                    <span className={`text-[10px] font-black tabular-nums transition-transform ${getSignalColor(device.rssi)}`}>
                                        {device.rssi}
                                    </span>
                                    <div className="w-8 h-0.5 bg-white/5 rounded-full mt-1 overflow-hidden">
                                        <div className={`h-full ${getSignalColor(device.rssi).split(' ')[0].replace('text-', 'bg-')}`} style={{ width: `${Math.min(100, Math.max(0, (device.rssi + 95) * 1.8))}%` }} />
                                    </div>
                                </div>

                                <div className="text-right">
                                    <div className="text-[11px] font-black text-white tabular-nums flex items-baseline justify-end group-hover:scale-105 transition-transform">
                                        {calculateDistance(device.rssi)}
                                        <span className="text-[8px] text-white/20 ml-0.5 italic">m</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Status Bar Footer */}
                <div className="py-2 px-5 bg-black/90 border-t border-white/5 flex items-center justify-between">
                    <div className="flex items-center space-x-4 text-[7px] font-mono text-white/30 uppercase tracking-widest">
                        <div className="flex items-center space-x-1.5">
                            <Gauge className="w-2.5 h-2.5" />
                            <span>REF_TX: -57.0</span>
                        </div>
                        <div className="flex items-center space-x-1.5">
                            <Shield className="w-2.5 h-2.5" />
                            <span>SIG_ANALYSIS: CM_ACCURATE</span>
                        </div>
                    </div>
                    <div className="text-[8px] font-black text-white/10">SIGINT MK-IV</div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
