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

// --- Provider ---

export const DetectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [alerts, setAlerts] = useState<DetectionEvent[]>([]);
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

        // Polling loop
        const interval = setInterval(refreshAlerts, 2000);
        return () => clearInterval(interval);
    }, [refreshAlerts]);

    return (
        <DetectionContext.Provider value={{ alerts, activeAlerts, selectedAlert, ackAlert, focusAlert, clearSelection }}>
            {children}
        </DetectionContext.Provider>
    );
};
