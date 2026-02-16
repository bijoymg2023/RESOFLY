import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  Info,
  CheckCircle,
  XCircle,
  Activity,
  Flame
} from 'lucide-react';
import { useDetection } from '@/contexts/DetectionContext';

const alertTypes = {
  LIFE: {
    icon: Activity,
    color: 'text-red-500',
    bgColor: 'bg-red-500/20'
  },
  FIRE: {
    icon: Flame,
    color: 'text-orange-500',
    bgColor: 'bg-orange-500/20'
  },
  error: {
    icon: XCircle,
    color: 'text-red-500',
    bgColor: 'bg-destructive/20'
  },
  warning: {
    icon: AlertTriangle,
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/20'
  },
  info: {
    icon: Info,
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/20'
  },
  success: {
    icon: CheckCircle,
    color: 'text-green-500',
    bgColor: 'bg-green-500/20'
  },
  vehicle: {
    icon: Info,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10'
  },
  other: {
    icon: Info,
    color: 'text-gray-400',
    bgColor: 'bg-gray-500/10'
  }
};

export const AlertBox = () => {
  const { alerts, clearAlerts } = useDetection();

  return (
    <Card className="bg-card/90 dark:bg-[#0A0A0A]/90 border border-border dark:border-white/10 backdrop-blur-sm flex flex-col overflow-hidden shadow-xl h-full">
      {/* Header */}
      <CardHeader className="py-3 px-4 border-b border-border dark:border-white/5 bg-muted/30 dark:bg-black/40 flex flex-row items-center justify-between shrink-0">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
          <CardTitle className="text-xs font-mono uppercase tracking-widest text-muted-foreground">Event Log</CardTitle>
        </div>
        <div className="flex items-center space-x-2">
          {alerts.length > 0 && (
            <button
              onClick={clearAlerts}
              className="text-[9px] font-mono px-2 py-0.5 rounded border border-red-500/30 text-red-400 hover:bg-red-500/20 hover:text-red-300 transition-colors tracking-wider"
            >
              CLEAR ALL
            </button>
          )}
          <Badge variant="outline" className="text-[10px] font-mono border-border dark:border-white/10 text-muted-foreground bg-muted/50 dark:bg-white/5">
            {alerts.length} EVENTS
          </Badge>
        </div>
      </CardHeader>

      {/* Scrollable Content */}
      <CardContent className="flex-1 p-0 bg-muted/20 dark:bg-black/50 font-mono text-xs overflow-y-auto min-h-0 relative">
        {/* CRT Scanline Effect (dark mode only) */}
        <div className="absolute inset-0 pointer-events-none z-10 opacity-0 dark:opacity-5 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))]" style={{ backgroundSize: "100% 2px, 3px 100%" }} />

        <div className="divide-y divide-border dark:divide-white/5">
          {alerts.length === 0 ? (
            <div className="text-muted-foreground italic p-6 text-center text-xs">
              <span>{'>'} Systems Normal... Awaiting Events</span>
            </div>
          ) : (
            alerts.map((alert) => {
              const config = alertTypes[alert.type] || alertTypes.info;
              const Icon = config.icon;

              return (
                <div
                  key={alert.id}
                  className="group flex items-center space-x-3 px-3 py-3 hover:bg-accent/10 dark:hover:bg-white/5 transition-colors cursor-default"
                >
                  <span className="text-muted-foreground shrink-0 font-mono text-[11px] tabular-nums w-[4.5rem]">
                    {alert.timestamp}
                  </span>
                  <span className={`uppercase font-bold shrink-0 text-[11px] ${config.color} flex items-center gap-1 w-20`}>
                    <Icon className="w-3.5 h-3.5" />
                    {alert.type}
                  </span>
                  <span className="text-foreground/80 dark:text-white/80 flex-1 text-[11px] truncate">
                    {(alert.type === 'LIFE' || alert.type === 'life')
                      ? `Human Signature (Conf: ${(alert.confidence * 100).toFixed(0)}%)`
                      : `Detection Event at ${alert.lat.toFixed(4)}, ${alert.lon.toFixed(4)}`
                    }
                  </span>
                </div>
              );
            })
          )}
        </div>

        {/* Terminal cursor */}
        <div className="text-muted-foreground/40 py-2 animate-pulse px-3 text-xs">_</div>
      </CardContent>
    </Card>
  );
};