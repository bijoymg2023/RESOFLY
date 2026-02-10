import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Bluetooth, RefreshCw, Smartphone, Signal, Search, X } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';

interface BluetoothDevice {
    mac: string;
    name: string;
    rssi: number;
}

const SignalTracker = () => {
    const [devices, setDevices] = useState<BluetoothDevice[]>([]);
    const [scanning, setScanning] = useState(false);
    const [target, setTarget] = useState<BluetoothDevice | null>(null);
    const [mockRssi, setMockRssi] = useState<number | null>(null); // For smooth animation

    const scan = async () => {
        setScanning(true);
        try {
            const res = await apiFetch('/api/scan/bluetooth');
            if (res.ok) {
                const data = await res.json();
                setDevices(data);
                // Only show toast if explicitly triggered by user, not initial load? 
                // Actually, helpful to know it scanned.
            } else {
                toast.error("Scan failed.");
            }
        } catch (e) {
            console.error(e);
            toast.error("Bluetooth scan error.");
        } finally {
            setScanning(false);
        }
    };

    // Auto-scan on mount
    useEffect(() => {
        scan();
        // Optional: Interval scanning?
        // const interval = setInterval(scan, 10000);
        // return () => clearInterval(interval);
    }, []);

    // tracker animation
    useEffect(() => {
        if (!target) {
            setMockRssi(null);
            return;
        }

        // Simulate slight fluctuation to make it feel "live" even if backend update is slow
        const interval = setInterval(() => {
            const base = target.rssi;
            const noise = Math.random() * 4 - 2; // +/- 2dB fluctuation
            setMockRssi(prev => {
                // Smooth lerp
                const current = prev ?? base;
                return current + (base + noise - current) * 0.1;
            });
        }, 100);

        return () => clearInterval(interval);
    }, [target]);

    const getSignalColor = (rssi: number) => {
        if (rssi > -60) return "text-emerald-500 drop-shadow-[0_0_8px_rgba(16,185,129,0.8)]"; // Strong
        if (rssi > -75) return "text-cyan-500"; // Medium
        if (rssi > -90) return "text-yellow-500"; // Weak
        return "text-red-500"; // Very Weak
    };

    return (
        <Card className="h-full bg-card/40 backdrop-blur-sm border-border dark:border-white/10 overflow-hidden flex flex-col shadow-lg">
            {/* Header - Darkened as requested */}
            <CardHeader className="py-3 px-4 flex flex-row items-center justify-between space-y-0 border-b border-white/10 bg-black/60">
                <div className="flex items-center space-x-2 text-muted-foreground">
                    <Bluetooth className="w-4 h-4" />
                    <CardTitle className="text-xs font-bold uppercase tracking-widest">Signal Tracker</CardTitle>
                </div>
                <div className="flex items-center space-x-1">
                    <div className={`w-2 h-2 rounded-full ${scanning ? 'bg-cyan-500 animate-pulse' : 'bg-muted'}`} />
                    <Badge variant="outline" className="text-[10px] h-5 border-white/10 bg-white/5">
                        {scanning ? 'SCANNING' : 'IDLE'}
                    </Badge>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-muted-foreground hover:text-foreground"
                        onClick={scan}
                        disabled={scanning}
                    >
                        <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} />
                    </Button>
                    {target && (
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-red-400 hover:text-red-300 hover:bg-red-900/20" onClick={() => setTarget(null)}>
                            <X className="w-3.5 h-3.5" />
                        </Button>
                    )}
                </div>
            </CardHeader>

            <CardContent className="p-0 flex-1 flex flex-col relative group">
                {/* Radar / Signal Visualizer area */}
                <div className="flex-1 min-h-[160px] bg-black/80 relative overflow-hidden flex items-center justify-center border-b border-white/10">
                    {/* Grid Overlay */}
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(0,255,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,255,0.05)_1px,transparent_1px)] bg-[size:20px_20px]" />

                    {/* Rotating Radar Sweep */}
                    {scanning && (
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                            <div className="w-[200%] h-[200%] bg-[conic-gradient(from_0deg,transparent_0deg,transparent_300deg,rgba(6,182,212,0.1)_360deg)] animate-[spin_4s_linear_infinite]" />
                        </div>
                    )}

                    {/* Concentric Circles */}
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
                        <div className="w-32 h-32 rounded-full border border-cyan-500" />
                        <div className="w-48 h-48 rounded-full border border-cyan-500" />
                        <div className="w-64 h-64 rounded-full border border-cyan-500" />
                    </div>

                    {target ? (
                        <div className="relative z-10 text-center animate-in fade-in zoom-in duration-300">
                            <div className="relative mb-2">
                                <div className="absolute -inset-4 bg-cyan-500/20 blur-xl rounded-full animate-pulse" />
                                <Smartphone className="w-12 h-12 mx-auto text-cyan-400 relative z-10" />
                            </div>

                            <div className={`text-5xl font-black font-mono tracking-tighter transition-colors duration-300 ${getSignalColor(mockRssi || -100)}`}>
                                {mockRssi ? Math.round(mockRssi) : target.rssi}
                                <span className="text-sm font-normal text-muted-foreground ml-1">dBm</span>
                            </div>

                            <div className="text-[10px] text-cyan-500/70 font-mono mt-1">{target.mac}</div>
                            <div className="mt-2 inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-white/10 text-white font-mono tracking-wider border border-white/10">
                                TARGET LOCKED
                            </div>
                        </div>
                    ) : (
                        <div className="text-center space-y-2 opacity-30 z-10">
                            <Signal className="w-12 h-12 mx-auto" />
                            <div className="text-[10px] uppercase tracking-widest">{scanning ? 'SCANNING...' : 'SYSTEM IDLE'}</div>
                            {scanning && <div className="text-[9px] font-mono text-cyan-500 animate-pulse">AQUIRING TARGETS</div>}
                        </div>
                    )}
                </div>

                {/* Device List - Terminal Style */}
                <div className="flex-1 bg-black/90 p-2 overflow-y-auto custom-scrollbar font-mono text-[10px]">
                    <div className="flex justify-between items-center mb-2 px-1 opacity-50 border-b border-white/10 pb-1">
                        <span>DETECTED SIGNALS</span>
                        <span>{devices.length} FOUND</span>
                    </div>

                    <div className="space-y-1">
                        {devices.map((device, i) => (
                            <div
                                key={i}
                                className={`flex justify-between items-center p-1.5 hover:bg-white/5 rounded cursor-pointer group transition-colors border border-transparent ${target?.mac === device.mac ? 'bg-cyan-900/20 border-cyan-500/50' : 'border-b border-white/5 last:border-0'}`}
                                onClick={() => setTarget(device)}
                            >
                                <div className="flex items-center space-x-2">
                                    <div className={`w-1.5 h-1.5 rounded-full ${device.rssi > -60 ? 'bg-emerald-500' : device.rssi > -80 ? 'bg-yellow-500' : 'bg-red-500'}`} />
                                    <span className={`font-bold ${target?.mac === device.mac ? 'text-cyan-400' : 'text-muted-foreground group-hover:text-white'}`}>
                                        {device.name || 'Unknown Device'}
                                    </span>
                                </div>
                                <div className="flex items-center space-x-3 text-muted-foreground group-hover:text-white transition-colors">
                                    <span className="opacity-50 hidden sm:inline">{device.mac}</span>
                                    <span className={`${device.rssi > -60 ? 'text-emerald-500' : device.rssi > -80 ? 'text-yellow-500' : 'text-red-500'}`}>
                                        {device.rssi}dBm
                                    </span>
                                </div>
                            </div>
                        ))}

                        {devices.length === 0 && !scanning && (
                            <div className="text-center py-6 text-muted-foreground/50">
                                NO SIGNAL
                            </div>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
