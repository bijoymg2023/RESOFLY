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

    return [
        {
            id: 'demo-1',
            type: 'LIFE',
            confidence: 0.94,
            max_temp: 36.8,
            lat: 12.9716,
            lon: 77.5946,
            ...makeTime(2),
            isActive: true,
        },
        {
            id: 'demo-2',
            type: 'FIRE',
            confidence: 0.87,
            max_temp: 312.5,
            lat: 12.9750,
            lon: 77.5900,
            ...makeTime(5),
            isActive: true,
        },
        {
            id: 'demo-3',
            type: 'LIFE',
            confidence: 0.91,
            max_temp: 37.2,
            lat: 12.9680,
            lon: 77.5980,
            ...makeTime(8),
            isActive: true,
        },
        {
            id: 'demo-4',
            type: 'FIRE',
            confidence: 0.78,
            max_temp: 285.0,
            lat: 12.9730,
            lon: 77.6020,
            ...makeTime(12),
            isActive: true,
        },
        {
            id: 'demo-5',
            type: 'LIFE',
            confidence: 0.96,
            max_temp: 36.5,
            lat: 12.9695,
            lon: 77.5870,
            ...makeTime(15),
            isActive: true,
        },
        {
            id: 'demo-6',
            type: 'LIFE',
            confidence: 0.82,
            max_temp: 35.9,
            lat: 12.9770,
            lon: 77.5960,
            ...makeTime(20),
            isActive: false,
        },
        {
            id: 'demo-7',
            type: 'FIRE',
            confidence: 0.89,
            max_temp: 340.1,
            lat: 12.9660,
            lon: 77.5920,
            ...makeTime(25),
            isActive: false,
        },
        {
            id: 'demo-8',
            type: 'LIFE',
            confidence: 0.73,
            max_temp: 34.8,
            lat: 12.9740,
            lon: 77.5850,
            ...makeTime(30),
            isActive: false,
        },
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
