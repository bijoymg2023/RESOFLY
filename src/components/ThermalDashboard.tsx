import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { VideoStreamBox } from './VideoStreamBox';
import { IncidentMap } from './IncidentMap';
import { AlertBox } from './AlertBox';
import { AlertsDetectionBox } from './AlertsDetectionBox';
import { GPSCoordinateBox } from './GPSCoordinateBox';
import { ThemeToggle } from './ThemeToggle';
import { useIsMobile } from '@/hooks/use-mobile';
import {
  Activity,
  Thermometer,
  AlertTriangle,
  Navigation,
  Monitor,
  Menu,
  X,
  Cpu,
  Globe,
  Wifi,
  Clock
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import { DetectionProvider } from '@/contexts/DetectionContext';

interface SystemStatus {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  temperature: number;
  uptime: number;
}

// Mini-Box Component for System Stats
const StatBox = ({ label, value, color, icon: Icon }: { label: string; value: string; color: string; icon: any }) => (
  <div className="bg-black/40 border border-white/5 rounded-lg p-3 flex flex-col justify-between h-full relative overflow-hidden group">
    <div className={`absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition-opacity ${color}`}>
      <Icon className="w-8 h-8" />
    </div>
    <div className="flex items-center space-x-2 mb-2">
      <Icon className={`w-4 h-4 ${color}`} />
      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</span>
    </div>
    <div>
      <div className={`text-2xl font-black font-mono tracking-tighter ${color}`}>
        {value}
      </div>
    </div>
    {value.includes('%') && (
      <div className="w-full h-1 bg-white/10 rounded-full mt-2 overflow-hidden">
        <div className={`h-full ${color.replace('text-', 'bg-')}`} style={{ width: value }} />
      </div>
    )}
  </div>
);

const formatUptime = (seconds: number) => {
  const d = Math.floor(seconds / (3600 * 24));
  const h = Math.floor((seconds % (3600 * 24)) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
};

const SystemStatusContent = () => {
  const { data: status } = useQuery<SystemStatus>({
    queryKey: ['status'],
    queryFn: async () => {
      const res = await apiFetch('/api/system-status');
      if (!res.ok) throw new Error('Failed to fetch stats');
      return res.json();
    },
    refetchInterval: 5000
  });

  if (!status) return <div className="text-xs p-4 text-center text-cyan-500 animate-pulse font-mono tracking-widest">SYSTEM INITIALIZING...</div>;

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/10">
        <div className="flex items-center space-x-2 text-muted-foreground">
          <Activity className="w-4 h-4" />
          <span className="text-xs font-bold uppercase tracking-widest">System Diagnostics</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] font-mono text-emerald-500">ONLINE</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 flex-1">
        <StatBox label="CPU Load" value={`${status.cpu_usage.toFixed(0)}%`} color={status.cpu_usage > 80 ? 'text-red-500' : 'text-cyan-500'} icon={Cpu} />
        <StatBox label="Memory" value={`${status.memory_usage.toFixed(0)}%`} color={status.memory_usage > 80 ? 'text-red-500' : 'text-purple-500'} icon={Activity} />
        <StatBox label="Thermal" value={`${status.temperature.toFixed(0)}°C`} color={status.temperature > 75 ? 'text-red-500' : 'text-emerald-500'} icon={Thermometer} />
        <StatBox label="Uptime" value={formatUptime(status.uptime).split(' ')[0]} color="text-white" icon={Clock} />
      </div>
    </div>
  );
};

import SignalTracker from './SignalTracker';

const ThermalDashboard = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isMobile = useIsMobile();

  return (
    <DetectionProvider>
      <div className="min-h-screen bg-background text-foreground font-sans selection:bg-cyan-500/30 relative overflow-hidden">
        <div className="absolute inset-0 z-0 opacity-[0.06] dark:opacity-[0.08] bg-[linear-gradient(to_right,currentColor_1px,transparent_1px),linear-gradient(to_bottom,currentColor_1px,transparent_1px)] bg-[size:3rem_3rem] pointer-events-none text-black dark:text-cyan-500" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[100vw] h-[500px] bg-primary/5 dark:bg-cyan-900/20 blur-[120px] rounded-full pointer-events-none" />

        <header className="relative z-50 flex items-center justify-between p-4 border-b border-border bg-card/80 backdrop-blur-md">
          <div className="flex items-center space-x-3">
            <div className="relative group">
              <div className="absolute inset-0 bg-cyan-500 blur opacity-40 group-hover:opacity-60 transition-opacity" />
              <div className="relative p-2 rounded-lg bg-black border border-cyan-500/50 text-cyan-400">
                <Globe className="h-5 w-5 animate-pulse-slow" />
              </div>
            </div>
            <div>
              <h1 className="text-xl font-black italic tracking-tighter text-foreground">RESOFLY</h1>
              <p className="text-[10px] text-muted-foreground uppercase tracking-[0.2em] hidden sm:block">Command & Control Link Established</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <div className="hidden sm:flex items-center space-x-3 text-[10px] font-mono text-emerald-500 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20">
              <Wifi className="w-3 h-3 animate-pulse" />
              <span>LINK STABLE</span>
            </div>
            <ThemeToggle />
            {isMobile && (
              <Button variant="outline" size="sm" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="sm:hidden border-white/10 bg-white/5 hover:bg-white/10 text-white">
                {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
              </Button>
            )}
          </div>
        </header>

        {isMobile && mobileMenuOpen && (
          <div className="fixed inset-0 top-16 bg-background/95 backdrop-blur-xl z-40 sm:hidden border-t border-border">
            <div className="p-4 space-y-3">
              {['Overview', 'Alerts', 'GPS Tracking'].map((item) => (
                <Button key={item} variant="ghost" className="w-full justify-start text-cyan-100 font-mono uppercase tracking-wider text-xs" onClick={() => setMobileMenuOpen(false)}>
                  <Monitor className="w-4 h-4 mr-2" />
                  {item}
                </Button>
              ))}
            </div>
          </div>
        )}

        <div className="relative z-10 p-2 sm:p-4 lg:p-6 space-y-4 lg:space-y-6 max-w-[1920px] mx-auto">
          <div className="flex flex-col space-y-6">

            {/* Top Tactical Strip (Video) */}
            <div className="w-full">
              <div className="aspect-video min-h-[400px] lg:min-h-[500px]">
                <VideoStreamBox />
              </div>
            </div>

            {/* UNIFIED 3x2 DIAGNOSTIC GRID */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 lg:gap-6">

              {/* Box 1: Global Positioning */}
              <div className="h-[350px] overflow-hidden rounded-xl border border-border bg-card/40 backdrop-blur-sm">
                <GPSCoordinateBox />
              </div>

              {/* Box 2: Signal Tracker */}
              <div className="h-[350px] overflow-hidden rounded-xl border border-border bg-card/40 backdrop-blur-sm">
                <SignalTracker />
              </div>

              {/* Box 3: System Diagnostics */}
              <Card className="bg-card/80 dark:bg-[#0A0A0A]/80 border-border dark:border-white/10 backdrop-blur-sm rounded-xl overflow-hidden shadow-sm h-[350px] flex flex-col justify-center">
                <CardContent className="p-6 h-full flex items-center">
                  <div className="w-full">
                    <SystemStatusContent />
                  </div>
                </CardContent>
              </Card>

              {/* Box 4: Tactical Map */}
              <div className="h-[350px] overflow-hidden rounded-xl border border-border bg-card/40 backdrop-blur-sm">
                <IncidentMap />
              </div>

              {/* Box 5: Event Log */}
              <div className="h-[350px] overflow-hidden rounded-xl border border-border bg-card/40 backdrop-blur-sm">
                <AlertBox />
              </div>

              {/* Box 6: Active Threats */}
              <div className="h-[350px] overflow-hidden rounded-xl border border-border bg-card/40 backdrop-blur-sm">
                <AlertsDetectionBox />
              </div>
            </div>

            {/* Mobile Actions Overlay */}
            <div className="lg:hidden grid grid-cols-2 gap-2 mt-4">
              <Button className="bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 h-10 flex items-center justify-center space-x-2">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-xs font-mono uppercase">Quick Alert</span>
              </Button>
              <Button className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 h-10 flex items-center justify-center space-x-2">
                <Navigation className="w-4 h-4" />
                <span className="text-xs font-mono uppercase">Locate</span>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </DetectionProvider>
  );
};

export default ThermalDashboard;