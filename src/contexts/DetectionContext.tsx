import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';

// --- Types ---

export interface DetectionEvent {
    id: string;
    type: 'LIFE' | 'FIRE' | 'vehicle' | 'other';
    confidence: number;
    max_temp: number;
    lat: number;
    lon: number;
    timestamp: string; // HH:MM:SS
    fullTimestamp: Date; // For sorting/filtering
    isActive: boolean; // True if it should show in the Alert Box
}

export interface DetectionContextType {
    alerts: DetectionEvent[]; // Full history
    activeAlerts: DetectionEvent[]; // Only active/recent for Alert Box
    selectedAlert: DetectionEvent | null; // For map focus
    ackAlert: (id: string) => void;
    focusAlert: (alert: DetectionEvent) => void;
    clearSelection: () => void;
}

// --- Context ---

const DetectionContext = createContext<DetectionContextType | undefined>(undefined);

export const useDetection = () => {
    const context = useContext(DetectionContext);
    if (!context) {
        throw new Error('useDetection must be used within a DetectionProvider');
    }
    return context;
};

// --- Demo Data for Demonstration ---

const generateDemoAlerts = (): DetectionEvent[] => {
    const now = new Date();
    const makeTime = (minsAgo: number) => {
        const t = new Date(now.getTime() - minsAgo * 60000);
        return {
            timestamp: t.toLocaleTimeString([], { hour12: false }),
            fullTimestamp: t
        };
    };

    // Center: Bangalore (approx Cubbon Park area)
    const centerLat = 12.9756;
    const centerLon = 77.5966;

    return [
        // --- RECENT CRITICAL ALERTS ---
        {
            id: 'demo-1',
            type: 'LIFE',
            confidence: 0.98,
            max_temp: 36.9, // Human body temp
            lat: centerLat + 0.001,
            lon: centerLon - 0.002,
            ...makeTime(1),
            isActive: true, // Just happened
        },
        {
            id: 'demo-2',
            type: 'FIRE',
            confidence: 0.92,
            max_temp: 420.5, // Significant fire
            lat: centerLat - 0.003,
            lon: centerLon + 0.001,
            ...makeTime(4),
            isActive: true,
        },
        {
            id: 'demo-3',
            type: 'LIFE',
            confidence: 0.85,
            max_temp: 37.1,
            lat: centerLat + 0.0015,
            lon: centerLon - 0.0025,
            ...makeTime(6),
            isActive: true,
        },

        // --- SECONDARY DETECTIONS ---
        {
            id: 'demo-4',
            type: 'vehicle',
            confidence: 0.89,
            max_temp: 85.0, // Engine block heat
            lat: centerLat + 0.004,
            lon: centerLon + 0.005, // Road area
            ...makeTime(10),
            isActive: true,
        },
        {
            id: 'demo-5',
            type: 'vehicle',
            confidence: 0.76,
            max_temp: 62.3, // Cooling engine or exhaust
            lat: centerLat + 0.0042,
            lon: centerLon + 0.0052,
            ...makeTime(12),
            isActive: true,
        },

        // --- OLDER / RESOLVED EVENTS ---
        {
            id: 'demo-6',
            type: 'LIFE',
            confidence: 0.65, // Lower confidence (maybe animal)
            max_temp: 38.2,
            lat: centerLat - 0.005,
            lon: centerLon - 0.005,
            ...makeTime(25),
            isActive: false, // Acknowledged
        },
        {
            id: 'demo-7',
            type: 'FIRE',
            confidence: 0.95,
            max_temp: 156.0, // Small handled fire / residue
            lat: centerLat - 0.0031, // Near the big fire
            lon: centerLon + 0.0011,
            ...makeTime(35),
            isActive: false,
        },
        {
            id: 'demo-8',
            type: 'other',
            confidence: 0.55,
            max_temp: 45.2, // HVAC vent or equipment
            lat: centerLat,
            lon: centerLon + 0.008,
            ...makeTime(45),
            isActive: false,
        },
        {
            id: 'demo-9',
            type: 'vehicle',
            confidence: 0.91,
            max_temp: 92.1,
            lat: centerLat + 0.006,
            lon: centerLon - 0.006,
            ...makeTime(50),
            isActive: false,
        },
        {
            id: 'demo-10',
            type: 'LIFE',
            confidence: 0.88,
            max_temp: 36.7,
            lat: centerLat - 0.002,
            lon: centerLon - 0.008,
            ...makeTime(60),
            isActive: false,
        }
    ];
};

export const DetectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [alerts, setAlerts] = useState<DetectionEvent[]>(generateDemoAlerts());
    const [selectedAlert, setSelectedAlert] = useState<DetectionEvent | null>(null);

    // Derived state for active alerts (unacknowledged)
    const activeAlerts = alerts.filter(a => a.isActive);

    // --- Actions ---

    const ackAlert = useCallback((id: string) => {
        setAlerts(prev => prev.map(a =>
            a.id === id ? { ...a, isActive: false } : a
        ));
    }, []);

    const focusAlert = useCallback((alert: DetectionEvent) => {
        setSelectedAlert(alert);
        // Optional: Auto-acknowledge on view? Maybe not, keep it manual for SAR.
        console.log("Focusing on alert:", alert.id);
    }, []);

    const clearSelection = useCallback(() => {
        setSelectedAlert(null);
    }, []);

    // --- Backend Integration ---

    // Function to fetch alerts from backend
    const refreshAlerts = useCallback(async () => {
        try {
            const token = localStorage.getItem('token');
            if (!token) return;

            const res = await fetch('/api/alerts', {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (res.ok) {
                const data = await res.json();

                // Map backend alerts to frontend DetectionEvent interface
                const mappedAlerts: DetectionEvent[] = data.map((a: any) => ({
                    id: a.id,
                    type: a.type.toUpperCase() as any, // 'life' -> 'LIFE'
                    confidence: a.confidence || 0.8,
                    max_temp: a.max_temp || 0,
                    lat: a.lat || 0,
                    lon: a.lon || 0,
                    timestamp: new Date(a.timestamp).toLocaleTimeString([], { hour12: false }),
                    fullTimestamp: new Date(a.timestamp),
                    isActive: !a.acknowledged
                }));

                // Update state only if changed (simple comparison)
                setAlerts(prev => {
                    const hasNew = mappedAlerts.some(ma => !prev.find(p => p.id === ma.id));
                    const stateChanged = mappedAlerts.length !== prev.length || hasNew;
                    return stateChanged ? mappedAlerts : prev;
                });
            }
        } catch (e) {
            console.error("Failed to sync alerts with backend:", e);
        }
    }, []);

    useEffect(() => {
        // Initial fetch
        refreshAlerts();

        // Polling loop (fallback for REST sync)
        const interval = setInterval(refreshAlerts, 5000); // Reduced frequency since we have WebSocket

        // WebSocket connection for instant alerts
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/alerts`;
        let ws: WebSocket | null = null;
        let reconnectTimer: NodeJS.Timeout | null = null;

        const connectWebSocket = () => {
            try {
                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    console.log('[WS] Connected to alert stream');
                };

                ws.onmessage = (event) => {
                    try {
                        const alert = JSON.parse(event.data);
                        console.log('[WS] Received alert:', alert);

                        // Add new alert immediately
                        const newAlert: DetectionEvent = {
                            id: alert.id,
                            type: (alert.type || 'LIFE').toUpperCase() as any,
                            confidence: alert.confidence || 0.8,
                            max_temp: alert.max_temp || alert.estimated_temp || 0,
                            lat: alert.lat || 0,
                            lon: alert.lon || 0,
                            timestamp: new Date(alert.timestamp).toLocaleTimeString([], { hour12: false }),
                            fullTimestamp: new Date(alert.timestamp),
                            isActive: true
                        };

                        setAlerts(prev => {
                            // Avoid duplicates
                            if (prev.find(a => a.id === newAlert.id)) {
                                return prev;
                            }
                            return [newAlert, ...prev];
                        });

                        // Show toast notification
                        toast.success(`🔥 ${alert.type} Detected!`, {
                            description: `${Math.round(alert.estimated_temp || 0)}°C | ${Math.round((alert.confidence || 0) * 100)}% confidence`
                        });
                    } catch (e) {
                        console.error('[WS] Parse error:', e);
                    }
                };

                ws.onclose = () => {
                    console.log('[WS] Disconnected, reconnecting in 3s...');
                    reconnectTimer = setTimeout(connectWebSocket, 3000);
                };

                ws.onerror = (err) => {
                    console.error('[WS] Error:', err);
                    ws?.close();
                };
            } catch (e) {
                console.error('[WS] Connection failed:', e);
                reconnectTimer = setTimeout(connectWebSocket, 3000);
            }
        };

        connectWebSocket();

        return () => {
            clearInterval(interval);
            if (reconnectTimer) clearTimeout(reconnectTimer);
            ws?.close();
        };
    }, [refreshAlerts]);

    return (
        <DetectionContext.Provider value={{ alerts, activeAlerts, selectedAlert, ackAlert, focusAlert, clearSelection }}>
            {children}
        </DetectionContext.Provider>
    );
};
