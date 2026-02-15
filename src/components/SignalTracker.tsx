import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
    Search, RefreshCw, Bluetooth, Signal, Smartphone, X, Target,
    Radar, SignalHigh, Cpu, SignalZero, Activity, Zap, Info
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

                // Update smoothed RSSI for active target
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

    // --- Smoothing & Distance Logic ---
    const calculateDistance = (rssi: number) => {
        // Environmental Params: 
        // tx_power (1m): -58 is realistic for typical indoor BLE/WiFi emitters
        // n (path loss exponent): 2.0 (Open) to 4.0 (Walls). Using 2.2 as average.
        const tx_power = -58;
        const n = 2.2;
        const d = Math.pow(10, (tx_power - rssi) / (10 * n));
        return d < 1 ? d.toFixed(2) : d.toFixed(1);
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
                // EMA alpha: 0.15 for super smooth, low-latency tracking
                const next = current + (raw - current) * 0.15;
                return next;
            });
        }, 100);

        return () => clearInterval(interval);
    }, [target?.mac, target?.rssi]);

    // History tracking
    useEffect(() => {
        if (smoothedRssi !== null) {
            setHistory(prev => [...prev.slice(-24), Math.round(smoothedRssi)]);
        }
    }, [smoothedRssi]);

    const getSignalColor = (rssi: number) => {
        if (rssi > -55) return "text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]";
        if (rssi > -70) return "text-cyan-400 drop-shadow-[0_0_6px_rgba(34,211,238,0.4)]";
        if (rssi > -85) return "text-amber-400";
        return "text-rose-500 drop-shadow-[0_0_4px_rgba(244,63,94,0.3)]";
    };

    const Sparkline = () => (
        <div className="flex items-end space-x-0.5 h-8 px-2">
            {[...Array(25)].map((_, i) => {
                const val = history[i] || -100;
                const height = Math.max(10, Math.min(100, (val + 100) * 1.5));
                return (
                    <div
                        key={i}
                        className={`w-1 rounded-t-full transition-all duration-500 ${val > -70 ? 'bg-cyan-500' : 'bg-white/10'}`}
                        style={{ height: `${height}%` }}
                    />
                );
            })}
        </div>
    );

    return (
        <Card className="h-full bg-zinc-950 border-white/5 overflow-hidden flex flex-col shadow-2xl relative">
            {/* HUD Corner Accents */}
            <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-cyan-500/40 z-50 rounded-tl-sm pointer-events-none" />
            <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-cyan-500/20 z-50 rounded-tr-sm pointer-events-none" />
            <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-cyan-500/10 z-50 rounded-bl-sm pointer-events-none" />

            <CardHeader className="py-2.5 px-4 flex flex-row items-center justify-between space-y-0 border-b border-white/5 bg-black/60 backdrop-blur-md">
                <div className="flex items-center space-x-3">
                    <Activity className={`w-3.5 h-3.5 text-cyan-500 ${scanning ? 'animate-pulse' : ''}`} />
                    <CardTitle className="text-[10px] font-black uppercase tracking-[0.25em] text-white/70">SigIntel Mk-II</CardTitle>
                </div>

                <div className="flex items-center space-x-3">
                    <div className="flex items-center space-x-1.5 px-2 py-0.5 bg-white/5 rounded-full border border-white/5">
                        <span className={`w-1 h-1 rounded-full ${scanning ? 'bg-cyan-500 animate-ping' : 'bg-muted'}`} />
                        <span className="text-[8px] font-black text-white/40 tracking-tighter">
                            {scanning ? 'UPLINK_LIVE' : 'NET_STANDBY'}
                        </span>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="p-0 flex-1 flex flex-col overflow-hidden relative">
                {/* Visualizer Area */}
                <div className="h-44 bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.05)_0,transparent_80%)] flex flex-col items-center justify-center relative overflow-hidden border-b border-white/5">
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(0,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,255,0.02)_1px,transparent_1px)] bg-[size:24px_24px]" />

                    {/* Concentric Signal Rings */}
                    <div className="absolute w-64 h-64 rounded-full border border-cyan-500/5 flex items-center justify-center pointer-events-none">
                        <div className="w-48 h-48 rounded-full border border-cyan-500/10 flex items-center justify-center">
                            <div className="w-32 h-32 rounded-full border border-cyan-500/20" />
                        </div>
                    </div>

                    {target ? (
                        <div className="relative z-10 flex flex-col items-center animate-in fade-in duration-700">
                            {/* Target Lock UI */}
                            <div className="absolute -top-12 -left-32 -right-32 flex justify-between px-10 pointer-events-none opacity-20">
                                <Zap className="w-4 h-4 text-cyan-500" />
                                <Target className="w-4 h-4 text-cyan-500" />
                            </div>

                            <div className="mb-2 relative group transition-transform duration-500">
                                <div className="absolute inset-0 bg-cyan-500/20 blur-2xl rounded-full scale-150 animate-pulse" />
                                <div className="relative p-2.5 bg-black/60 rounded-lg border border-cyan-500/40 backdrop-blur-md">
                                    {target.type === 'wifi' ? <SignalHigh className="w-6 h-6 text-cyan-400" /> : <Bluetooth className="w-6 h-6 text-blue-400" />}
                                </div>
                            </div>

                            <div className={`text-6xl font-black font-mono tracking-tighter tabular-nums flex items-end leading-none ${getSignalColor(smoothedRssi || -100)}`}>
                                {calculateDistance(smoothedRssi || target.rssi)}
                                <span className="text-sm font-bold ml-1 text-white/30 tracking-widest uppercase mb-1">Meters</span>
                            </div>

                            <div className="mt-3 flex flex-col items-center">
                                <Sparkline />
                                <div className="mt-2 text-[9px] font-mono text-cyan-500/60 uppercase tracking-widest flex items-center space-x-2">
                                    <span className="font-black text-white px-1 bg-white/10 rounded">LOCK</span>
                                    <span>{target.mac}</span>
                                    <span className="text-white/30">•</span>
                                    <span>{Math.round(smoothedRssi || 0)} dBm</span>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="relative z-10 text-center flex flex-col items-center">
                            <div className="w-16 h-16 rounded-full border-2 border-dashed border-white/5 animate-[spin_10s_linear_infinite] mb-4 flex items-center justify-center">
                                <Cpu className="w-6 h-6 text-white/10" />
                            </div>
                            <div className="text-[10px] font-black uppercase tracking-[0.4em] text-white/20">Awaiting Signal...</div>
                        </div>
                    )}
                </div>

                {/* Signals Table */}
                <div className="flex-1 overflow-auto custom-scrollbar bg-black/40">
                    <div className="grid grid-cols-[1fr_70px_60px] px-5 py-2 text-[9px] font-black uppercase text-white/20 tracking-[0.2em] border-b border-white/5 sticky top-0 bg-zinc-950/90 backdrop-blur-xl z-20">
                        <span>Emitter_ID</span>
                        <span className="text-center">Energy</span>
                        <span className="text-right">Prox</span>
                    </div>

                    <div className="p-2 space-y-1.5">
                        {devices.map((device, i) => (
                            <div
                                key={i}
                                className={`group grid grid-cols-[1fr_70px_60px] items-center px-3 py-2.5 rounded-md cursor-pointer transition-all duration-300 relative border ${target?.mac === device.mac ? 'bg-cyan-500/5 border-cyan-500/20' : 'bg-white/[0.01] border-transparent hover:bg-white/[0.04] hover:border-white/5'}`}
                                onClick={() => setTarget(device)}
                            >
                                <div className="flex items-center space-x-4 overflow-hidden">
                                    <div className={`p-1.5 rounded bg-black/40 border ${target?.mac === device.mac ? 'border-cyan-500/40 text-cyan-400' : 'border-white/5 text-white/30'} group-hover:border-cyan-500/30 transition-colors`}>
                                        {device.type === 'wifi' ? <Signal className="w-3 h-3" /> : <Bluetooth className="w-3 h-3" />}
                                    </div>
                                    <div className="flex flex-col min-w-0">
                                        <span className={`text-[11px] font-bold transition-colors truncate ${target?.mac === device.mac ? 'text-white' : 'text-white/60 group-hover:text-white'}`}>
                                            {device.name || 'ANON_CLIENT'}
                                        </span>
                                        <span className="text-[8px] font-mono text-white/20 uppercase tracking-tighter">{device.mac}</span>
                                    </div>
                                </div>

                                <div className="flex flex-col items-center">
                                    <span className={`text-[10px] font-black tabular-nums ${getSignalColor(device.rssi)}`}>
                                        {device.rssi}
                                    </span>
                                    <div className="w-10 h-0.5 bg-white/5 rounded-full mt-1 overflow-hidden">
                                        <div
                                            className={`h-full opacity-60 ${getSignalColor(device.rssi).split(' ')[0].replace('text-', 'bg-')}`}
                                            style={{ width: `${Math.min(100, Math.max(0, (device.rssi + 95) * 2))}%` }}
                                        />
                                    </div>
                                </div>

                                <div className="text-right">
                                    <div className="text-[11px] font-black text-white tabular-nums flex items-baseline justify-end">
                                        {calculateDistance(device.rssi)}
                                        <span className="text-[8px] font-bold text-white/20 ml-0.5 italic">m</span>
                                    </div>
                                </div>
                            </div>
                        ))}

                        {devices.length === 0 && !scanning && (
                            <div className="flex flex-col items-center justify-center py-16 opacity-10">
                                <Radar className="w-10 h-10 mb-2 rotate-45" />
                                <div className="text-[10px] font-black uppercase tracking-[0.3em]">No Emitters Found</div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Status Bar Footer */}
                <div className="py-2 px-4 bg-black/60 border-t border-white/5 flex items-center justify-between text-[8px] font-mono">
                    <div className="flex items-center space-x-4">
                        <div className="flex items-center space-x-1 text-emerald-500/60">
                            <Zap className="w-2.5 h-2.5" />
                            <span>AUTO_CAL_ACTIVE</span>
                        </div>
                        <div className="flex items-center space-x-1 text-white/20">
                            <Info className="w-2.5 h-2.5" />
                            <span>TX_REF: -58dB</span>
                        </div>
                    </div>
                    <div className="text-white/10 uppercase tracking-widest font-black">Secure Signal Intel</div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
