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
  Wifi
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

// Custom HUD Progress Bar
const HUDBar = ({ value, color = "bg-cyan-500" }: { value: number; color?: string }) => (
  <div className="flex-1 h-1.5 bg-[#1a1a1a] rounded-sm overflow-hidden border border-white/5 relative">
    <div
      className={`h-full ${color} shadow-[0_0_10px_rgba(34,211,238,0.5)] transition-all duration-500`}
      style={{ width: `${value}%` }}
    />
    <div className="absolute inset-0 bg-[linear-gradient(90deg,transparent_2px,#000_1px)] bg-[size:4px_100%] opacity-50" />
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

  if (!status) return <div className="text-[10px] p-4 text-center text-cyan-500/50 animate-pulse font-mono">INITIALIZING TELEMETRY...</div>;

  return (
    <div className="space-y-4 font-mono">
      {/* CPU */}
      <div className="space-y-1">
        <div className="flex justify-between items-center text-[10px] uppercase tracking-wider text-cyan-200/70">
          <span className="flex items-center"><Cpu className="w-3 h-3 mr-1.5 opacity-70" /> CPU Load</span>
          <span>{status.cpu_usage.toFixed(1)}%</span>
        </div>
        <HUDBar value={status.cpu_usage} color={status.cpu_usage > 80 ? "bg-red-500" : "bg-cyan-500"} />
      </div>

      {/* Memory */}
      <div className="space-y-1">
        <div className="flex justify-between items-center text-[10px] uppercase tracking-wider text-cyan-200/70">
          <span className="flex items-center"><Activity className="w-3 h-3 mr-1.5 opacity-70" /> Memory</span>
          <span>{status.memory_usage.toFixed(1)}%</span>
        </div>
        <HUDBar value={status.memory_usage} color={status.memory_usage > 80 ? "bg-red-500" : "bg-cyan-500"} />
      </div>

      {/* Temp */}
      <div className="space-y-1">
        <div className="flex justify-between items-center text-[10px] uppercase tracking-wider text-cyan-200/70">
          <span className="flex items-center"><Thermometer className="w-3 h-3 mr-1.5 opacity-70" /> Core Temp</span>
          <span>{status.temperature.toFixed(1)}°C</span>
        </div>
        <HUDBar value={(status.temperature / 100) * 100} color={status.temperature > 75 ? "bg-red-500" : "bg-emerald-500"} />
      </div>

      {/* Footer Info */}
      <div className="pt-3 mt-3 border-t border-white/5 grid grid-cols-2 gap-2">
        <div className="bg-white/5 rounded p-2 text-center border border-white/5">
          <div className="text-[10px] text-white/30 uppercase">Uptime</div>
          <div className="text-xs text-white">{formatUptime(status.uptime)}</div>
        </div>
        <div className="bg-white/5 rounded p-2 text-center border border-white/5">
          <div className="text-[10px] text-white/30 uppercase">Network</div>
          <div className="text-xs text-emerald-400">SECURE</div>
        </div>
      </div>
    </div>
  );
};

const ThermalDashboard = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isMobile = useIsMobile();

  return (
    <DetectionProvider>
      <div className="min-h-screen bg-background text-foreground font-sans selection:bg-cyan-500/30 relative overflow-hidden">

        {/* --- Background Elements --- */}
        <div className="absolute inset-0 z-0 opacity-10 bg-[linear-gradient(to_right,#00bcd4_1px,transparent_1px),linear-gradient(to_bottom,#00bcd4_1px,transparent_1px)] bg-[size:3rem_3rem] [mask-image:radial-gradient(ellipse_80%_60%_at_50%_0%,#000_60%,transparent_100%)] pointer-events-none" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[100vw] h-[500px] bg-cyan-900/20 blur-[120px] rounded-full pointer-events-none" />


        {/* --- Header --- */}
        <header className="relative z-50 flex items-center justify-between p-4 border-b border-border bg-card/80 backdrop-blur-md">
          <div className="flex items-center space-x-3">
            <div className="relative group">
              <div className="absolute inset-0 bg-cyan-500 blur opacity-40 group-hover:opacity-60 transition-opacity" />
              <div className="relative p-2 rounded-lg bg-black border border-cyan-500/50 text-cyan-400">
                <Globe className="h-5 w-5 animate-pulse-slow" />
              </div>
            </div>
            <div>
              <h1 className="text-xl font-black italic tracking-tighter text-foreground">
                RESOFLY
              </h1>
              <p className="text-[10px] text-muted-foreground uppercase tracking-[0.2em] hidden sm:block">
                Command & Control Link Established
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="hidden sm:flex items-center space-x-3 text-[10px] font-mono text-emerald-500 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20">
              <Wifi className="w-3 h-3 animate-pulse" />
              <span>LINK STABLE</span>
            </div>
            <ThemeToggle />

            {/* Mobile menu button */}
            {isMobile && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="sm:hidden border-white/10 bg-white/5 hover:bg-white/10 text-white"
              >
                {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
              </Button>
            )}
          </div>
        </header>

        {/* --- Mobile Nav --- */}
        {isMobile && mobileMenuOpen && (
          <div className="fixed inset-0 top-16 bg-background/95 backdrop-blur-xl z-40 sm:hidden border-t border-border">
            <div className="p-4 space-y-3">
              {['Overview', 'Alerts', 'GPS Tracking'].map((item) => (
                <Button key={item} variant="ghost" className="w-full justify-start text-cyan-100 hover:text-cyan-400 hover:bg-cyan-900/20 font-mono uppercase tracking-wider text-xs border border-transparent hover:border-cyan-500/30" onClick={() => setMobileMenuOpen(false)}>
                  <Monitor className="w-4 h-4 mr-2" />
                  {item}
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* --- Main Dashboard Content --- */}
        <div className="relative z-10 p-2 sm:p-4 lg:p-6 space-y-4 lg:space-y-6 max-w-[1920px] mx-auto">

          {/* Main Layout - Responsive Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6">

            {/* LEFT: Video Stream - Takes more space on larger screens */}
            <div className="lg:col-span-8 xl:col-span-9">
              <div className="aspect-video min-h-[300px] sm:min-h-[400px] lg:min-h-[500px]">
                <VideoStreamBox />
              </div>
            </div>

            {/* RIGHT: GPS & System Status - Stacks on mobile, sidebar on desktop */}
            <div className="lg:col-span-4 xl:col-span-3 space-y-4 lg:space-y-6">

              {/* GPS Unit */}
              <div className="rounded-xl overflow-hidden border border-border bg-card/40 backdrop-blur-sm">
                <GPSCoordinateBox />
              </div>

              {/* System Status Panel */}
              <Card className="bg-card/80 dark:bg-[#0A0A0A]/80 border-border dark:border-white/10 backdrop-blur-sm rounded-xl overflow-hidden shadow-2xl">
                <div className="p-3 lg:p-4 border-b border-border dark:border-white/5 flex justify-between items-center bg-muted/20 dark:bg-white/[0.02]">
                  <div className="flex items-center space-x-2 text-cyan-500 dark:text-cyan-400">
                    <Monitor className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-widest">System Diagnostics</span>
                  </div>
                  <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 dark:bg-cyan-400 animate-pulse" />
                </div>
                <CardContent className="p-3 sm:p-4 lg:p-6">
                  <SystemStatusContent />
                </CardContent>
              </Card>

              {/* Mobile Actions - Only shows below lg */}
              <div className="lg:hidden grid grid-cols-2 gap-2">
                <Button className="bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 h-10 flex items-center justify-center space-x-2">
                  <AlertTriangle className="w-4 h-4" />
                  <span className="text-xs font-mono uppercase">Quick Alert</span>
                </Button>
                <Button className="bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 h-10 flex items-center justify-center space-x-2">
                  <Navigation className="w-4 h-4" />
                  <span className="text-xs font-mono uppercase">Locate</span>
                </Button>
              </div>
            </div>
          </div>

          {/* Bottom Section: 3 Boxes - Bigger, scrollable, polished */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 lg:gap-6">
            <div className="min-h-[300px] h-[45vh] max-h-[550px] overflow-hidden">
              <IncidentMap />
            </div>
            <div className="min-h-[300px] h-[45vh] max-h-[550px] overflow-hidden">
              <AlertBox />
            </div>
            <div className="min-h-[300px] h-[45vh] max-h-[550px] overflow-hidden sm:col-span-2 lg:col-span-1">
              <AlertsDetectionBox />
            </div>
          </div>
        </div>
      </div>
    </DetectionProvider>
  );
};

export default ThermalDashboard;