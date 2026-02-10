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

            <CardContent className="p-0 flex-1 flex flex-col relative">

                {/* Radar / Signal Visualizer */}
                <div className="flex-1 min-h-[140px] bg-black/50 dark:bg-black/80 relative overflow-hidden flex items-center justify-center border-b border-border dark:border-white/5">
                    {/* Grid */}
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:20px_20px]" />

                    {target ? (
                        <div className="relative text-center z-10 space-y-2">
                            {/* Signal Arc */}
                            <div className="flex items-end justify-center space-x-1 h-12 mb-2">
                                {[1, 2, 3, 4, 5].map(i => (
                                    <div
                                        key={i}
                                        className={`w-2 rounded-sm transition-all duration-300 ${i <= bars ? getSignalColor(mockRssi || -100).replace('text-', 'bg-') : 'bg-white/10'}`}
                                        style={{ height: `${i * 20}%` }}
                                    />
                                ))}
                            </div>

                            <div className={`text-4xl font-black font-mono tracking-tighter transition-colors duration-300 ${getSignalColor(mockRssi || -100)}`}>
                                {mockRssi ? Math.round(mockRssi) : target.rssi}
                                <span className="text-sm font-normal text-muted-foreground ml-1">dBm</span>
                            </div>
                            <div className="text-[10px] bg-white/10 px-2 py-0.5 rounded text-white/70 font-mono tracking-wider">
                                {target.rssi > -60 ? "PROXIMITY ALERT" : "TRACKING..."}
                            </div>
                        </div>
                    ) : (
                        <div className="text-center space-y-2 opacity-30">
                            <Signal className="w-12 h-12 mx-auto" />
                            <div className="text-[10px] uppercase tracking-widest">No Target Locked</div>
                        </div>
                    )}
                </div>

                {/* Device List */}
                <div className="flex-1 min-h-[120px] bg-card/60 overflow-y-auto custom-scrollbar p-1">
                    {devices.length === 0 && !scanning ? (
                        <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-[10px] space-y-2 p-4">
                            <Search className="w-8 h-8 opacity-20" />
                            <span>Scan to detect nearby devices</span>
                            <Button variant="outline" size="sm" onClick={scan} className="mt-2 text-xs border-dashed h-7">Start Scan</Button>
                        </div>
                    ) : (
                        <div className="space-y-1 p-1">
                            {devices.map((dev) => (
                                <div
                                    key={dev.mac}
                                    onClick={() => setTarget(dev)}
                                    className={`
                                group flex items-center justify-between p-2 rounded cursor-pointer transition-all border
                                ${target?.mac === dev.mac
                                            ? 'bg-blue-500/10 border-blue-500/30'
                                            : 'hover:bg-accent/50 border-transparent hover:border-border dark:hover:border-white/5'}
                            `}
                                >
                                    <div className="flex items-center space-x-3 overflow-hidden">
                                        <div className={`p-1.5 rounded-full ${target?.mac === dev.mac ? 'bg-blue-500 text-white' : 'bg-muted text-muted-foreground'}`}>
                                            {dev.name.toLowerCase().includes('phone') ? <Smartphone className="w-3.5 h-3.5" /> :
                                                dev.name.toLowerCase().includes('unknown') ? <HelpCircle className="w-3.5 h-3.5" /> :
                                                    <Bluetooth className="w-3.5 h-3.5" />}
                                        </div>
                                        <div className="min-w-0">
                                            <div className={`text-xs font-semibold truncate ${target?.mac === dev.mac ? 'text-blue-400' : 'text-foreground'}`}>
                                                {dev.name || "Unknown Device"}
                                            </div>
                                            <div className="text-[9px] font-mono text-muted-foreground truncate opacity-70">
                                                {dev.mac}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center space-x-2">
                                        <div className={`text-xs font-mono font-bold ${getSignalColor(dev.rssi)}`}>
                                            {dev.rssi}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

export default SignalTracker;
