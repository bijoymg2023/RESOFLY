import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
    Search,
    RefreshCw,
    Bluetooth,
    Signal,
    Smartphone,
    X,
    Target,
    Radar,
    SignalHigh,
    Cpu,
    SignalZero
} from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { toast } from 'sonner';
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
    const [mockRssi, setMockRssi] = useState<number | null>(null);

    const scan = async () => {
        setScanning(true);
        try {
            const res = await apiFetch('/api/scan/bluetooth');
            if (res.ok) {
                const data = await res.json();
                setDevices(data);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setScanning(false);
        }
    };

    useEffect(() => {
        scan();
        const interval = setInterval(scan, 10000);
        return () => clearInterval(interval);
    }, []);

    const calculateDistance = (rssi: number) => {
        // Precise formula: tx = -40, n = 2.0
        const d = Math.pow(10, (-40 - rssi) / (20.0));
        return d.toFixed(1);
    };

    useEffect(() => {
        if (!target) {
            setMockRssi(null);
            return;
        }
        const interval = setInterval(() => {
            const base = target.rssi;
            const noise = Math.random() * 2 - 1;
            setMockRssi(prev => {
                const current = prev ?? base;
                return current + (base + noise - current) * 0.1;
            });
        }, 100);
        return () => clearInterval(interval);
    }, [target]);

    const getSignalColor = (rssi: number) => {
        if (rssi > -50) return "text-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.6)]";
        if (rssi > -65) return "text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.5)]";
        if (rssi > -80) return "text-amber-400";
        return "text-rose-500";
    };

    return (
        <Card className="h-full bg-black/40 backdrop-blur-md border-white/5 overflow-hidden flex flex-col shadow-2xl relative">
            {/* Background Glitch / Scanning Effect */}
            <div className="absolute top-0 left-0 w-full h-1 bg-cyan-500/20 animate-[scanline_3s_linear_infinite] pointer-events-none z-50" />

            <CardHeader className="py-2.5 px-4 flex flex-row items-center justify-between space-y-0 border-b border-white/10 bg-gradient-to-r from-black/80 to-black/40 backdrop-blur-xl">
                <div className="flex items-center space-x-3">
                    <div className="relative">
                        <Radar className={`w-4 h-4 text-cyan-400 ${scanning ? 'animate-pulse' : ''}`} />
                        {scanning && <div className="absolute -inset-1 bg-cyan-400/20 blur-sm rounded-full animate-ping" />}
                    </div>
                    <CardTitle className="text-[10px] font-black uppercase tracking-[0.2em] text-white/90">Signal Tracker</CardTitle>
                </div>

                <div className="flex items-center space-x-2">
                    <Badge variant="outline" className={`text-[9px] h-5 border-white/10 ${scanning ? 'bg-cyan-500/10 text-cyan-400' : 'bg-white/5 text-white/40'}`}>
                        {scanning ? 'LINK ACTIVE' : 'STANDBY'}
                    </Badge>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 rounded-full bg-white/5 hover:bg-white/10 border border-white/5"
                        onClick={scan}
                        disabled={scanning}
                    >
                        <RefreshCw className={`w-3.5 h-3.5 text-cyan-400 ${scanning ? 'animate-spin' : ''}`} />
                    </Button>
                </div>
            </CardHeader>

            <CardContent className="p-0 flex-1 flex flex-col overflow-hidden">
                {/* Visualizer Area */}
                <div className="h-44 bg-zinc-950 flex flex-col items-center justify-center relative overflow-hidden border-b border-white/5">
                    {/* Retro Grid */}
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.1)_0,transparent_70%)] opacity-50" />
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(0,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,255,0.03)_1px,transparent_1px)] bg-[size:16px_16px]" />

                    {/* Animated Radar Sweep */}
                    <div className="absolute w-[300px] h-[300px] pointer-events-none opacity-40">
                        <div className="absolute inset-0 rounded-full border border-cyan-500/20" />
                        <div className="absolute inset-8 rounded-full border border-cyan-500/15" />
                        <div className="absolute inset-16 rounded-full border border-cyan-500/10" />
                        {scanning && <div className="absolute inset-0 bg-[conic-gradient(from_0deg,transparent_0deg,transparent_320deg,rgba(6,182,212,0.3)_360deg)] animate-[spin_4s_linear_infinite] rounded-full" />}
                    </div>

                    {target ? (
                        <div className="relative z-10 flex flex-col items-center animate-in fade-in zoom-in-95 duration-500">
                            {/* Target Icon with Glow */}
                            <div className="relative mb-3">
                                <div className="absolute inset-0 bg-cyan-400/30 blur-2xl rounded-full animate-pulse" />
                                <div className="relative p-3 bg-cyan-950/40 rounded-xl border border-cyan-500/50 backdrop-blur-xl">
                                    {target.type === 'wifi' ? <SignalHigh className="w-8 h-8 text-cyan-400" /> : <Bluetooth className="w-8 h-8 text-blue-400" />}
                                </div>
                            </div>

                            {/* Distance Metric - Primary */}
                            <div className={`text-6xl font-black font-mono tracking-tighter tabular-nums flex items-baseline ${getSignalColor(mockRssi || -100)}`}>
                                {calculateDistance(mockRssi || target.rssi)}
                                <span className="text-xl font-bold ml-1 text-white/40 tracking-normal italic">m</span>
                            </div>

                            <div className="mt-1 space-y-0.5 text-center">
                                <div className="text-[9px] font-bold text-white tracking-widest uppercase flex items-center justify-center space-x-2">
                                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                                    <span>Target Locked</span>
                                </div>
                                <div className="text-[8px] font-mono text-white/30 truncate max-w-[150px]">
                                    {target.mac} • {target.name}
                                </div>
                            </div>

                            {/* Tech Badges */}
                            <div className="absolute top-0 right-4 flex flex-col space-y-1 opacity-60">
                                <div className="text-[8px] font-mono text-cyan-500">TX_PWR: -40dB</div>
                                <div className="text-[8px] font-mono text-cyan-500">RSSI: {Math.round(mockRssi || target.rssi)}dBm</div>
                            </div>
                        </div>
                    ) : (
                        <div className="relative z-10 text-center opacity-40">
                            <Cpu className="w-10 h-10 mx-auto text-cyan-500/50 mb-2" />
                            <div className="text-[9px] font-black uppercase tracking-[0.3em] text-white">Searching Network...</div>
                        </div>
                    )}
                </div>

                {/* Signals Table */}
                <div className="flex-1 overflow-auto custom-scrollbar bg-black/20">
                    <div className="grid grid-cols-[1fr_80px_60px] px-4 py-2 text-[9px] font-black uppercase text-white/30 tracking-widest border-b border-white/5 sticky top-0 bg-zinc-950/80 backdrop-blur-md z-10">
                        <span>Identifier</span>
                        <span className="text-center">Signal</span>
                        <span className="text-right">Dist</span>
                    </div>

                    <div className="p-1.5 space-y-1">
                        {devices.map((device, i) => (
                            <div
                                key={i}
                                className={`group grid grid-cols-[1fr_80px_60px] items-center px-2 py-2 rounded-lg cursor-pointer transition-all duration-300 relative border ${target?.mac === device.mac ? 'bg-cyan-500/10 border-cyan-500/30' : 'bg-white/[0.02] border-transparent hover:bg-white/[0.05] hover:border-white/5'}`}
                                onClick={() => setTarget(device)}
                            >
                                <div className="flex items-center space-x-3 overflow-hidden">
                                    <div className="relative">
                                        <div className={`w-1.5 h-1.5 rounded-full ${device.type === 'wifi' ? 'bg-cyan-500' : 'bg-blue-500'}`} />
                                        {target?.mac === device.mac && <div className="absolute inset-0 bg-cyan-500 blur-sm rounded-full animate-ping" />}
                                    </div>
                                    <div className="flex flex-col min-w-0">
                                        <span className="text-[10px] font-bold text-white group-hover:text-cyan-400 transition-colors truncate">
                                            {device.name || 'Unknown'}
                                        </span>
                                        <span className="text-[8px] font-mono text-white/30 truncate">{device.mac}</span>
                                    </div>
                                </div>

                                <div className="flex flex-col items-center">
                                    <div className={`text-[10px] font-black tabular-nums ${getSignalColor(device.rssi)}`}>
                                        {device.rssi}<span className="text-[8px] opacity-40 ml-0.5">dB</span>
                                    </div>
                                    <div className="w-12 h-1 bg-white/5 rounded-full mt-1 overflow-hidden">
                                        <div
                                            className={`h-full ${getSignalColor(device.rssi).split(' ')[0].replace('text-', 'bg-')}`}
                                            style={{ width: `${Math.min(100, Math.max(0, (device.rssi + 100) * 1.5))}%` }}
                                        />
                                    </div>
                                </div>

                                <div className="text-right">
                                    <span className="text-[11px] font-black text-white tabular-nums group-hover:scale-110 transition-transform inline-block">
                                        {calculateDistance(device.rssi)}
                                        <span className="text-[8px] font-bold text-white/30 ml-0.5">m</span>
                                    </span>
                                </div>
                            </div>
                        ))}

                        {devices.length === 0 && !scanning && (
                            <div className="flex flex-col items-center justify-center py-12 opacity-20">
                                <SignalZero className="w-8 h-8 mb-2" />
                                <div className="text-[9px] font-bold uppercase tracking-widest">No Active Signals</div>
                            </div>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
