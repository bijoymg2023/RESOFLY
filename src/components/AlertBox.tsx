import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useIsMobile } from '@/hooks/use-mobile';
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
  const { alerts } = useDetection();

  return (
    <Card className="bg-[#0A0A0A]/90 border border-white/10 backdrop-blur-sm flex flex-col overflow-hidden shadow-xl h-full min-h-[280px]">
      <CardHeader className="py-3 px-4 border-b border-white/5 bg-black/40 flex flex-row items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
          <CardTitle className="text-xs font-mono uppercase tracking-widest text-white/60">Event Log</CardTitle>
        </div>
        <Badge variant="outline" className="text-[10px] font-mono border-white/10 text-white/40 bg-white/5">
          {alerts.length} EVENTS
        </Badge>
      </CardHeader>

      <CardContent className="flex-1 p-0 bg-black/50 font-mono text-xs overflow-hidden relative min-h-0">
        {/* CRT Scanline Effect */}
        <div className="absolute inset-0 pointer-events-none z-10 opacity-5 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))]" style={{ backgroundSize: "100% 2px, 3px 100%" }} />

        <ScrollArea className="h-full w-full">
          <div className="space-y-0 p-1">
            {alerts.length === 0 ? (
              <div className="text-white/20 italic p-4 text-center text-xs">
                <span>{'>'} System Systems Normal...</span>
              </div>
            ) : (
              alerts.map((alert) => {
                const config = alertTypes[alert.type] || alertTypes.info;
                const Icon = config.icon;

                return (
                  <div
                    key={alert.id}
                    className={`group flex items-start space-x-3 px-3 py-2.5 hover:bg-white/5 transition-colors cursor-default border-b border-white/5 last:border-0`}
                  >
                    <span className="text-white/30 shrink-0 font-mono text-xs w-16">
                      {alert.timestamp}
                    </span>
                    <span className={`uppercase font-bold shrink-0 text-xs ${config.color} flex items-center w-24`}>
                      <Icon className="w-3 h-3 mr-1" />
                      {alert.type}
                    </span>
                    <span className="text-white/80 flex-1 truncate text-xs">
                      {alert.type === 'LIFE'
                        ? `Human Signature (Conf: ${(alert.confidence * 100).toFixed(0)}%)`
                        : `Detection Event at ${alert.lat.toFixed(4)}, ${alert.lon.toFixed(4)}`
                      }
                    </span>
                  </div>
                );
              })
            )}
            <div className="text-white/20 pt-2 animate-pulse px-2">_</div>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};