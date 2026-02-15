import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
    Search, RefreshCw, Bluetooth, Signal, Smartphone, X, Target,
    Radar, SignalHigh, Cpu, SignalZero, Activity, Zap, Info, Shield, Gauge
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

    // --- Advanced Signal Logic ---
    const calculateDistance = (rssi: number) => {
        // Tuned for Pi 4 + Smartphone indoors
        const tx_power = -59.5;
        const n = 2.4;
        const d = Math.pow(10, (tx_power - rssi) / (10 * n));
        return d < 1 ? d.toFixed(2) : d.toFixed(1);
    };

    const getReliability = (rssi: number) => {
        // Heuristic: -30 to -60 is high, -85 is low
        const score = Math.max(0, Math.min(100, (rssi + 95) * 1.5));
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
                const next = current + (raw - current) * 0.12; // Slower smoothing = more stability
                return next;
            });
        }, 100);

        return () => clearInterval(interval);
    }, [target?.mac, target?.rssi]);

    useEffect(() => {
        if (smoothedRssi !== null) {
            setHistory(prev => [...prev.slice(-30), Math.round(smoothedRssi)]);
        }
    }, [smoothedRssi]);

    const getSignalColor = (rssi: number) => {
        if (rssi > -60) return "text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.4)]";
        if (rssi > -75) return "text-emerald-400";
        if (rssi > -85) return "text-amber-400";
        return "text-rose-500";
    };

    const Sparkline = () => (
        <div className="flex items-end space-x-0.5 h-6 px-1 opacity-60">
            {[...Array(30)].map((_, i) => {
                const val = history[i] || -100;
                const height = Math.max(15, Math.min(100, (val + 100) * 1.4));
                return (
                    <div
                        key={i}
                        className={`w-[2px] rounded-t-full transition-all duration-700 ${val > -70 ? 'bg-cyan-500' : 'bg-white/5'}`}
                        style={{ height: `${height}%` }}
                    />
                );
            })}
        </div>
    );

    return (
        <Card className="h-full bg-black/80 border-white/5 overflow-hidden flex flex-col shadow-2xl relative font-sans">
            {/* Top HUD Frame */}
            <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/30 to-transparent" />
            <div className="absolute top-0 left-4 w-12 h-2 border-l border-t border-cyan-500/20" />
            <div className="absolute top-0 right-4 w-12 h-2 border-r border-t border-cyan-500/20" />

            <CardHeader className="py-2.5 px-5 flex flex-row items-center justify-between space-y-0 border-b border-white/5 bg-zinc-950/40 backdrop-blur-xl">
                <div className="flex items-center space-x-2.5">
                    <div className="p-1.5 bg-cyan-500/10 rounded-sm border border-cyan-500/20">
                        <Radar className={`w-3 h-3 text-cyan-400 ${scanning ? 'animate-spin' : ''}`} />
                    </div>
                    <CardTitle className="text-[9px] font-black uppercase tracking-[0.4em] text-cyan-500/70">SigIntel Analysis</CardTitle>
                </div>

                <div className="flex items-center space-x-3">
                    <div className="text-[8px] font-mono text-white/20 uppercase tracking-widest hidden sm:block">
                        SYS_LOCK: {target ? 'ENGAGED' : 'READY'}
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 rounded bg-white/5 hover:bg-cyan-500/20 border border-white/5"
                        onClick={scan}
                    >
                        <RefreshCw className={`w-3 h-3 text-cyan-500 ${scanning ? 'animate-spin' : ''}`} />
                    </Button>
                </div>
            </CardHeader>

            <CardContent className="p-0 flex-1 flex flex-col overflow-hidden relative">
                {/* Visualizer Area */}
                <div className="h-40 bg-zinc-950/60 flex flex-col items-center justify-center relative overflow-hidden border-b border-white/5">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.03)_0,transparent_75%)]" />
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(0,255,255,0.01)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,255,0.01)_1px,transparent_1px)] bg-[size:32px_32px]" />

                    {target ? (
                        <div className="relative z-10 flex flex-col items-center animate-in fade-in duration-1000">
                            {/* Proportional Grid Overlay */}
                            <div className="absolute -inset-10 border border-cyan-500/5 rounded-full pointer-events-none opacity-50" />

                            <div className="mb-1.5 flex flex-row items-center space-x-2 text-[8px] font-mono text-cyan-500/40 uppercase tracking-[0.2em]">
                                <Shield className="w-2.5 h-2.5" />
                                <span>Locked Target Verified</span>
                            </div>

                            {/* Meters Display - Reduced Size */}
                            <div className={`text-4xl font-black font-mono tracking-tighter tabular-nums flex items-baseline leading-none ${getSignalColor(smoothedRssi || -100)}`}>
                                {calculateDistance(smoothedRssi || target.rssi)}
                                <span className="text-xs font-bold ml-1.5 text-white/20 tracking-normal uppercase mb-1">Meters</span>
                            </div>

                            <div className="mt-4 flex flex-col items-center w-full max-w-[200px]">
                                <div className="flex items-center justify-between w-full mb-1 px-1">
                                    <span className="text-[7px] font-bold text-white/20 uppercase">Trend</span>
                                    <span className="text-[7px] font-bold text-cyan-500/40">{getReliability(smoothedRssi || target.rssi)}% Quality</span>
                                </div>
                                <Sparkline />
                                <div className="w-full h-[1px] bg-gradient-to-r from-transparent via-white/10 to-transparent mt-3" />
                                <div className="mt-2 text-[8px] font-mono text-white/40 uppercase truncate flex items-center space-x-3">
                                    <Badge variant="outline" className="h-3 text-[6px] px-1 border-white/10 bg-white/5 text-white/60">ADDR: {target.mac}</Badge>
                                    <span>Signal: {Math.round(smoothedRssi || 0)} dBm</span>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="relative z-10 text-center flex flex-col items-center opacity-40">
                            <div className="relative w-12 h-12 flex items-center justify-center">
                                <div className="absolute inset-0 border-2 border-dashed border-cyan-500/20 rounded-full animate-[spin_15s_linear_infinite]" />
                                <SignalZero className="w-5 h-5 text-white/20" />
                            </div>
                            <div className="mt-3 text-[8px] font-black uppercase tracking-[0.5em] text-white/30">Network Pulse Standby</div>
                        </div>
                    )}
                </div>

                {/* Signals Table */}
                <div className="flex-1 overflow-auto custom-scrollbar bg-black/40 px-3 pt-2">
                    <div className="flex items-center justify-between px-2 pb-2 border-b border-white/5">
                        <span className="text-[8px] font-black uppercase text-white/20 tracking-[0.2em]">Detected Emitters</span>
                        <span className="text-[8px] text-white/10">{devices.length} Found</span>
                    </div>

                    <div className="py-2 space-y-1">
                        {devices.map((device, i) => (
                            <div
                                key={i}
                                className={`group grid grid-cols-[1fr_60px_50px] items-center px-3 py-2 rounded transition-all duration-300 border ${target?.mac === device.mac ? 'bg-cyan-500/5 border-cyan-500/20' : 'bg-transparent border-transparent hover:bg-white/[0.03]'}`}
                                onClick={() => setTarget(device)}
                            >
                                <div className="flex items-center space-x-3 overflow-hidden">
                                    <div className={`p-1 rounded-sm border ${target?.mac === device.mac ? 'border-cyan-500/40 text-cyan-500' : 'border-white/5 text-white/20'}`}>
                                        {device.type === 'wifi' ? <Signal className="w-2.5 h-2.5" /> : <Bluetooth className="w-2.5 h-2.5" />}
                                    </div>
                                    <div className="flex flex-col min-w-0">
                                        <span className={`text-[10px] font-bold transition-colors truncate ${target?.mac === device.mac ? 'text-white' : 'text-white/50 group-hover:text-white/80'}`}>
                                            {device.name || 'ANONYMOUS_OBJ'}
                                        </span>
                                        <span className="text-[7px] font-mono text-white/10">{device.mac}</span>
                                    </div>
                                </div>

                                <div className="flex flex-col items-center">
                                    <span className={`text-[9px] font-black tabular-nums group-hover:scale-110 transition-transform ${getSignalColor(device.rssi)}`}>
                                        {device.rssi}
                                    </span>
                                    <div className="w-8 h-0.5 bg-white/5 rounded-full mt-1 overflow-hidden opacity-50">
                                        <div className={`h-full ${getSignalColor(device.rssi).split(' ')[0].replace('text-', 'bg-')}`} style={{ width: `${Math.min(100, Math.max(0, (device.rssi + 90) * 2))}%` }} />
                                    </div>
                                </div>

                                <div className="text-right">
                                    <div className="text-[10px] font-black text-white/70 tabular-nums">
                                        {calculateDistance(device.rssi)}
                                        <span className="text-[7px] text-white/20 ml-0.5 uppercase tracking-tighter italic font-light">m</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Footer HUD */}
                <div className="py-2 px-4 bg-zinc-950/80 border-t border-white/5 flex items-center justify-between">
                    <div className="flex items-center space-x-3 text-[7px] font-mono opacity-40">
                        <div className="flex items-center space-x-1">
                            <Zap className="w-2 h-2 text-cyan-500" />
                            <span>AUTO_RE_OFF</span>
                        </div>
                        <div className="flex items-center space-x-1">
                            <Gauge className="w-2 h-2" />
                            <span>REF: -59.5dB</span>
                        </div>
                    </div>
                    <div className="text-[7px] font-black text-white/10 tracking-[0.3em] uppercase">SigIntel Protocol V2</div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
