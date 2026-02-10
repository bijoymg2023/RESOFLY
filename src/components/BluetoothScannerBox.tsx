import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Bluetooth, RefreshCw, Signal, Target, ArrowLeft, Smartphone } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { apiFetch } from '@/lib/api';

interface BluetoothDevice {
    mac: string;
    name: string;
    rssi: number;
}

export const BluetoothScannerBox = () => {
    const [devices, setDevices] = useState<BluetoothDevice[]>([]);
    const [scanning, setScanning] = useState(false);
    const [selectedDevice, setSelectedDevice] = useState<BluetoothDevice | null>(null);
    const [lastScanTime, setLastScanTime] = useState<Date | null>(null);

    const scanDevices = async () => {
        setScanning(true);
        try {
            const res = await apiFetch('/api/scan/bluetooth');
            if (res.ok) {
                const data = await res.json();
                // Sort by RSSI (closest first)
                const sorted = data.sort((a: BluetoothDevice, b: BluetoothDevice) => b.rssi - a.rssi);
                setDevices(sorted);
                setLastScanTime(new Date());

                // Update selected device if it still exists
                if (selectedDevice) {
                    const updated = sorted.find((d: BluetoothDevice) => d.mac === selectedDevice.mac);
                    if (updated) setSelectedDevice(updated);
                }
            }
        } catch (e) {
            console.error("Scan failed", e);
        } finally {
            setScanning(false);
        }
    };

    // Auto-scan if tracking a device
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (selectedDevice) {
            interval = setInterval(scanDevices, 2000); // Fast scan when tracking
        }
        return () => clearInterval(interval);
    }, [selectedDevice]);

    // Signal strength color helper
    const getSignalColor = (rssi: number) => {
        if (rssi > -60) return "text-emerald-500 bg-emerald-500/20 border-emerald-500/50"; // Very Close
        if (rssi > -75) return "text-yellow-500 bg-yellow-500/20 border-yellow-500/50";   // Nearby
        return "text-red-500 bg-red-500/20 border-red-500/50";                             // Far
    };

    const getSignalPercent = (rssi: number) => {
        // Map -100 (0%) to -40 (100%)
        return Math.min(Math.max((rssi + 100) * (100 / 60), 0), 100);
    };

    return (
        <Card className="h-full bg-card/80 dark:bg-[#0A0A0A]/90 border-border dark:border-white/10 backdrop-blur-sm rounded-xl overflow-hidden shadow-2xl flex flex-col">
            {/* Header */}
            <div className="p-3 lg:p-4 border-b border-border dark:border-white/5 flex justify-between items-center bg-muted/20 dark:bg-white/[0.02]">
                <div className="flex items-center space-x-2 text-blue-500 dark:text-blue-400">
                    <Bluetooth className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-widest">Signal Tracker</span>
                </div>
                {!selectedDevice && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={scanDevices}
                        disabled={scanning}
                        className="h-6 w-6 p-0 hover:bg-blue-500/20 text-blue-400"
                    >
                        <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} />
                    </Button>
                )}
            </div>

            <CardContent className="p-0 flex-1 relative overflow-hidden flex flex-col h-[280px]">
                {selectedDevice ? (
                    /* --- TRACKING MODE --- */
                    <div className="flex flex-col h-full bg-black/40">
                        {/* Top Bar */}
                        <div className="p-4 border-b border-white/5 flex items-center justify-between bg-black/20">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSelectedDevice(null)}
                                className="text-muted-foreground hover:text-white hover:bg-white/10 -ml-2 h-8"
                            >
                                <ArrowLeft className="w-4 h-4 mr-1" /> Back
                            </Button>
                            <div className="flex flex-col items-end">
                                <span className="text-xs font-bold text-white tracking-wider">{selectedDevice.name || 'Unknown Device'}</span>
                                <span className="text-[10px] text-muted-foreground font-mono">{selectedDevice.mac}</span>
                            </div>
                        </div>

                        {/* Signal Meter */}
                        <div className="flex-1 flex flex-col items-center justify-center p-6 relative">
                            {/* Animated Rings */}
                            <div className={`absolute inset-0 flex items-center justify-center transition-all duration-500 opacity-20 pointer-events-none`}>
                                <div className={`w-32 h-32 rounded-full border-2 ${getSignalColor(selectedDevice.rssi).split(' ')[0]} animate-ping absolute`} />
                                <div className={`w-48 h-48 rounded-full border border-white/5 absolute`} />
                                <div className={`w-64 h-64 rounded-full border border-white/5 absolute`} />
                            </div>

                            <div className="text-center z-10 space-y-2">
                                <div className={`text-6xl font-black font-mono tracking-tighter ${getSignalColor(selectedDevice.rssi).split(' ')[0]}`}>
                                    {selectedDevice.rssi}
                                </div>
                                <div className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground">Signal Strength (dBm)</div>
                            </div>
                        </div>

                        {/* Footer Bar */}
                        <div className="h-2 w-full bg-black/50 overflow-hidden relative">
                            <div
                                className={`h-full transition-all duration-300 ${getSignalColor(selectedDevice.rssi).split(' ')[0].replace('text-', 'bg-')}`}
                                style={{ width: `${getSignalPercent(selectedDevice.rssi)}%` }}
                            />
                        </div>
                    </div>
                ) : (
                    /* --- LIST MODE --- */
                    <ScrollArea className="h-full">
                        <div className="p-2 space-y-1">
                            {devices.length === 0 && !scanning && (
                                <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground opacity-50 space-y-2">
                                    <Signal className="w-8 h-8" />
                                    <span className="text-[10px] uppercase tracking-wider">No Signals Detected</span>
                                    <Button variant="outline" size="sm" onClick={scanDevices} className="mt-2 text-xs border-white/10">Start Scan</Button>
                                </div>
                            )}

                            {devices.map((device) => (
                                <div
                                    key={device.mac}
                                    onClick={() => setSelectedDevice(device)}
                                    className="group flex items-center justify-between p-3 rounded-lg border border-transparent hover:border-blue-500/30 hover:bg-blue-500/5 cursor-pointer transition-all duration-200 bg-black/20"
                                >
                                    <div className="flex items-center space-x-3">
                                        <div className={`p-2 rounded-md ${getSignalColor(device.rssi)}`}>
                                            <Smartphone className="w-4 h-4" />
                                        </div>
                                        <div className="flex flex-col">
                                            <span className="text-xs font-bold text-foreground group-hover:text-blue-400 transition-colors">
                                                {device.name || 'Unknown Device'}
                                            </span>
                                            <span className="text-[10px] text-muted-foreground font-mono">{device.mac}</span>
                                        </div>
                                    </div>

                                    <div className="flex flex-col items-end space-y-1">
                                        <span className={`text-xs font-mono font-bold ${getSignalColor(device.rssi).split(' ')[0]}`}>
                                            {device.rssi} dBm
                                        </span>
                                        <div className="w-16 h-1 bg-black/50 rounded-full overflow-hidden">
                                            <div
                                                className={`h-full ${getSignalColor(device.rssi).split(' ')[0].replace('text-', 'bg-')}`}
                                                style={{ width: `${getSignalPercent(device.rssi)}%` }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </ScrollArea>
                )}
            </CardContent>
        </Card>
    );
};
