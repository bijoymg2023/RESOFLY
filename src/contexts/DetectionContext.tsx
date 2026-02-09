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

    // --- Simulation Logic (Mock Backend) ---

    useEffect(() => {
        // Simulate incoming detection events
        const interval = setInterval(() => {
            // 30% chance to trigger a detection every 3 seconds
            if (Math.random() > 0.7) {
                const now = new Date();
                const isLife = Math.random() > 0.3; // 70% chance of LIFE detection
                const type: 'LIFE' | 'FIRE' = isLife ? 'LIFE' : 'FIRE';

                // Base coords sim: 12.9716° N, 77.5946° E (Bangalore approx)
                // Add some jitter
                const lat = 12.9716 + (Math.random() - 0.5) * 0.01;
                const lon = 77.5946 + (Math.random() - 0.5) * 0.01;

                const newEvent: DetectionEvent = {
                    id: Math.random().toString(36).substr(2, 9),
                    type,
                    confidence: 0.6 + Math.random() * 0.35, // 0.6 - 0.95
                    max_temp: isLife ? 36 + Math.random() * 4 : 80 + Math.random() * 50,
                    lat,
                    lon,
                    timestamp: now.toLocaleTimeString([], { hour12: false }),
                    fullTimestamp: now,
                    isActive: true
                };

                setAlerts(prev => {
                    const recentDuplicate = prev.find(a =>
                        a.isActive &&
                        a.type === newEvent.type &&
                        Math.abs(a.lat - newEvent.lat) < 0.0005 &&
                        Math.abs(a.lon - newEvent.lon) < 0.0005 &&
                        (now.getTime() - a.fullTimestamp.getTime()) < 30000
                    );

                    if (recentDuplicate) {
                        console.log("Duplicate detection suppressed");
                        return prev;
                    }

                    if (newEvent.type === 'LIFE') {
                        // console.log("Life detected!"); 
                    }

                    return [newEvent, ...prev].slice(0, 100); // Keep last 100
                });
            }
        }, 3000);

        return () => clearInterval(interval);
    }, [focusAlert]);

    return (
        <DetectionContext.Provider value={{ alerts, activeAlerts, selectedAlert, ackAlert, focusAlert, clearSelection }}>
            {children}
        </DetectionContext.Provider>
    );
};
