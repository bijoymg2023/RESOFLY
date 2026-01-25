import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useIsMobile } from '@/hooks/use-mobile';
import { apiFetch } from '@/lib/api';
import {
  AlertTriangle,
  Info,
  CheckCircle,
  XCircle,
  Clock,
  X,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface Alert {
  id: string;
  type: 'error' | 'warning' | 'info' | 'success';
  title: string;
  message: string;
  timestamp: Date;
  acknowledged: boolean;
}

const alertTypes = {
  error: {
    icon: XCircle,
    color: 'destructive',
    bgColor: 'bg-destructive/20',
    borderColor: 'border-destructive/30',
    textColor: 'text-destructive'
  },
  warning: {
    icon: AlertTriangle,
    color: 'warning',
    bgColor: 'bg-warning/20',
    borderColor: 'border-warning/30',
    textColor: 'text-warning'
  },
  info: {
    icon: Info,
    color: 'primary',
    bgColor: 'bg-primary/20',
    borderColor: 'border-primary/30',
    textColor: 'text-primary'
  },
  success: {
    icon: CheckCircle,
    color: 'success',
    bgColor: 'bg-success/20',
    borderColor: 'border-success/30',
    textColor: 'text-success'
  }
};

const API_URL = '/api';

export const AlertBox = () => {
  const [expandedAlert, setExpandedAlert] = useState<string | null>(null);
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();

  // Fetch Alerts
  const { data: alerts = [] } = useQuery<Alert[]>({
    queryKey: ['alerts'],
    queryFn: async () => {
      const res = await apiFetch(`${API_URL}/alerts`);
      if (!res.ok) throw new Error('Failed to fetch alerts');
      const data = await res.json();
      // Ensure timestamps are Date objects
      return data.map((alert: any) => ({
        ...alert,
        timestamp: new Date(alert.timestamp)
      }));
    },
    refetchInterval: 5000,
  });

  // Acknowledge Mutation
  const acknowledgeMutation = useMutation({
    mutationFn: async (alertId: string) => {
      await apiFetch(`${API_URL}/alerts/${alertId}/acknowledge`, { method: 'PATCH' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    }
  });

  // Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: async (alertId: string) => {
      await fetch(`${API_URL}/alerts/${alertId}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    }
  });

  const acknowledgeAlert = (alertId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    acknowledgeMutation.mutate(alertId);
  };

  return (
    <Card className="h-full bg-[#0A0A0A]/90 border border-white/10 backdrop-blur-sm flex flex-col overflow-hidden shadow-xl">
      <CardHeader className="py-3 px-4 border-b border-white/5 bg-black/40 flex flex-row items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
          <CardTitle className="text-xs font-mono uppercase tracking-widest text-white/60">System Events Log</CardTitle>
        </div>
        <Badge variant="outline" className="text-[10px] font-mono border-white/10 text-white/40 bg-white/5">
          {alerts.length} EVENTS
        </Badge>
      </CardHeader>

      <CardContent className="flex-1 p-0 bg-black/50 font-mono text-xs overflow-hidden relative">
        {/* CRT Scanline Effect */}
        <div className="absolute inset-0 pointer-events-none z-10 opacity-5 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))]" style={{ backgroundSize: "100% 2px, 3px 100%" }} />

        <ScrollArea className="flex-1 w-full h-full pr-4">
          <div className="space-y-1">
            {alerts.length === 0 ? (
              <div className="text-white/20 italic p-2 text-center text-xs">
                <span>{'>'} System Systems Normal...</span>
              </div>
            ) : (
              alerts.map((alert) => {
                const config = alertTypes[alert.type];
                return (
                  <div
                    key={alert.id}
                    className={`group flex items-start space-x-3 p-2 hover:bg-white/5 rounded transition-colors cursor-default ${alert.acknowledged ? 'opacity-40' : 'opacity-100'}`}
                  >
                    <span className="text-white/30 shrink-0 font-mono text-xs">
                      {alert.timestamp.toLocaleTimeString([], { hour12: false })}
                    </span>
                    <span className={`uppercase font-bold shrink-0 text-xs ${config.textColor}`}>
                      {alert.type}
                    </span>
                    <span className="text-white/80 flex-1 truncate text-xs">
                      {alert.message}
                    </span>

                    {/* Hover Actions */}
                    <div className="opacity-0 group-hover:opacity-100 flex items-center space-x-2 transition-opacity">
                      {!alert.acknowledged && (
                        <button
                          onClick={(e) => acknowledgeAlert(alert.id, e)}
                          className="text-[10px] uppercase bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded text-white/70"
                        >
                          ACK
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
            <div className="text-white/20 pt-2 animate-pulse">_</div>
          </div>
        </ScrollArea>
      </CardContent >
    </Card >
  );
};