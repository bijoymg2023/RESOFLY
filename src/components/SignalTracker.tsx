import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Bluetooth, RefreshCw, Smartphone, HelpCircle, Signal, Wifi, Search, X } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { toast } from 'sonner';

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
                if (data.length === 0) toast.info("No devices found nearby.");
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
        if (rssi > -60) return "text-red-500 drop-shadow-[0_0_8px_rgba(239,68,68,0.8)]"; // HOT
        if (rssi > -75) return "text-orange-500"; // WARM
        if (rssi > -90) return "text-yellow-500"; // COLD
        return "text-slate-500"; // FREEZING
    };

    const getSignalBars = (rssi: number) => {
        // 5 bars
        // > -50: 5
        // > -60: 4
        // > -70: 3
        // > -80: 2
        // > -90: 1
        // else 0
        if (rssi > -50) return 5;
        if (rssi > -60) return 4;
        if (rssi > -70) return 3;
        if (rssi > -80) return 2;
        if (rssi > -90) return 1;
        return 0;
    };

    const bars = target ? getSignalBars(target.rssi) : 0;

    return (
        <Card className="h-full bg-card/40 backdrop-blur-sm border-border dark:border-white/10 overflow-hidden flex flex-col shadow-lg">
            <CardHeader className="py-3 px-4 flex flex-row items-center justify-between space-y-0 border-b border-border dark:border-white/5 bg-muted/20">
                <div className="flex items-center space-x-2 text-blue-500 dark:text-blue-400">
                    <Bluetooth className="w-4 h-4" />
                    <CardTitle className="text-xs font-bold uppercase tracking-widest">Signal Tracker</CardTitle>
                </div>
                <div className="flex space-x-2">
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

            <CardContent className="p-0 flex-1 flex flex-col relative bg-black">

                {/* Radar / Signal Visualizer */}
                <div className="flex-1 min-h-[160px] relative overflow-hidden flex items-center justify-center border-b border-white/10 group">

                    {/* Radar Grid */}
                    <div className="absolute inset-0 bg-[radial-gradient(circle,rgba(34,211,238,0.1)_1px,transparent_1px)] bg-[size:20px_20px] opacity-30" />
                    <div className="absolute inset-0 border-[0.5px] border-cyan-500/20 rounded-full m-4" />
                    <div className="absolute inset-0 border-[0.5px] border-cyan-500/10 rounded-full m-12" />
                    <div className="absolute inset-0 border-[0.5px] border-cyan-500/5 rounded-full m-20" />

                    {/* Scanning Animation */}
                    {(scanning || !target) && (
                        <div className="absolute inset-0 m-4 rounded-full animate-spin-slow bg-[conic-gradient(from_0deg,transparent_0deg,transparent_270deg,rgba(34,211,238,0.2)_360deg)]" />
                    )}

                    {target ? (
                        <div className="relative text-center z-10 space-y-1">
                            {/* Signal Arc */}
                            <div className="flex items-end justify-center space-x-1 h-12 mb-2">
                                {[1, 2, 3, 4, 5].map(i => (
                                    <div
                                        key={i}
                                        className={`w-2.5 rounded-sm transition-all duration-300 ${i <= bars ? getSignalColor(mockRssi || -100).replace('text-', 'bg-') : 'bg-white/5'}`}
                                        style={{ height: `${i * 20}%` }}
                                    />
                                ))}
                            </div>

                            <div className={`text-5xl font-black font-mono tracking-tighter transition-colors duration-300 ${getSignalColor(mockRssi || -100)}`}>
                                {mockRssi ? Math.round(mockRssi) : target.rssi}
                                <span className="text-sm font-normal text-muted-foreground ml-1">dBm</span>
                            </div>
                            <div className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-white/10 text-white font-mono tracking-wider border border-white/10">
                                {target.rssi > -60 ? "PROXIMITY ALERT" : "TRACKING SIGNAL"}
                            </div>
                        </div>
                    ) : (
                        <div className="text-center space-y-3 opacity-40 z-10">
                            <div className="relative">
                                <Search className={`w-8 h-8 mx-auto text-cyan-500 ${scanning ? 'animate-pulse' : ''}`} />
                                {scanning && <div className="absolute inset-0 bg-cyan-500 blur-xl opacity-50 animate-pulse" />}
                            </div>
                            <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-500">
                                {scanning ? "SCANNING FREQUENCIES..." : "SYSTEM IDLE"}
                            </div>
                        </div>
                    )}
                </div>

                {/* Device List - Terminal Style */}
                <div className="flex-1 min-h-[140px] bg-black font-mono text-xs relative overflow-hidden">
                    {/* Scanlines Effect */}
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%] pointer-events-none z-20 opacity-20" />

                    <div className="absolute top-0 left-0 right-0 bg-white/5 px-2 py-1 text-[9px] text-muted-foreground border-b border-white/5 flex justify-between">
                        <span>DETECTED SIGNALS</span>
                        <span>{devices.length} FOUND</span>
                    </div>

                    <div className="h-full overflow-y-auto custom-scrollbar p-2 pt-8 space-y-1">
                        {devices.length === 0 && !scanning ? (
                            <div className="flex flex-col items-center justify-center h-full text-muted-foreground/30 space-y-2">
                                <div className="text-[10px] text-center">
                                    NO SIGNAL DETECTED<br />
                                    INITIATE SCAN SEQUENCE
                                </div>
                                <Button variant="outline" size="sm" onClick={scan} className="h-6 text-[10px] border-dashed border-white/20 hover:bg-white/5">
                                    INITIATE
                                </Button>
                            </div>
                        ) : (
                            devices.map((dev, i) => (
                                <div
                                    key={dev.mac}
                                    onClick={() => setTarget(dev)}
                                    className={`
                                group flex items-center justify-between p-2 rounded-sm cursor-pointer transition-all border border-transparent
                                ${target?.mac === dev.mac
                                            ? 'bg-cyan-950/30 border-cyan-500/30 text-cyan-400'
                                            : 'hover:bg-white/5 hover:border-white/10 text-muted-foreground hover:text-cyan-200'}
                            `}
                                >
                                    <div className="flex items-center space-x-2 min-w-0">
                                        <span className="text-[9px] opacity-50 w-4">{(i + 1).toString().padStart(2, '0')}</span>
                                        <div className="truncate">
                                            <div className="font-bold truncate">{dev.name || "UNKNOWN_DEVICE"}</div>
                                            <div className="text-[9px] opacity-50">{dev.mac}</div>
                                        </div>
                                    </div>
                                    <div className={`text-right font-bold tabular-nums ${getSignalColor(dev.rssi)}`}>
                                        {dev.rssi} <span className="text-[9px] opacity-50">dB</span>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
