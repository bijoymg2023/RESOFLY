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
  <div className="flex-1 h-1.5 bg-muted dark:bg-[#1a1a1a] rounded-sm overflow-hidden border border-border dark:border-white/5 relative">
    <div
      className={`h-full ${color} shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-500`}
      style={{ width: `${value}%` }}
    />
    <div className="absolute inset-0 bg-[linear-gradient(90deg,transparent_2px,hsl(var(--background))_1px)] bg-[size:4px_100%] opacity-30 dark:opacity-50" />
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

// Circular Progress Component
const CircularProgress = ({ value, label, color, subtext, icon: Icon }: { value: number; label: string; color: string; subtext: string; icon: any }) => {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (value / 100) * circumference;

  return (
    <div className="flex flex-col items-center justify-center p-2">
      <div className="relative w-12 h-12 mb-1">
        {/* Background Circle */}
        <svg className="w-full h-full transform -rotate-90">
          <circle
            cx="24"
            cy="24"
            r={radius}
            stroke="currentColor"
            strokeWidth="3"
            fill="transparent"
            className="text-muted/20"
          />
          {/* Progress Circle */}
          <circle
            cx="24"
            cy="24"
            r={radius}
            stroke="currentColor"
            strokeWidth="3"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className={`${color} transition-all duration-1000 ease-out`}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <Icon className={`w-4 h-4 ${color}`} />
        </div>
      </div>
      <div className="text-xs font-bold font-mono">{value}%</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</div>
    </div>
  );
};

// Revamped System Status Panel
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
    <div className="grid grid-cols-4 gap-2 divide-x divide-border/50 dark:divide-white/5">
      <CircularProgress
        value={status.cpu_usage}
        label="CPU"
        color={status.cpu_usage > 80 ? 'text-red-500' : 'text-cyan-500'}
        subtext={`${status.cpu_usage.toFixed(0)}%`}
        icon={Cpu}
      />

      <CircularProgress
        value={status.memory_usage}
        label="RAM"
        color={status.memory_usage > 80 ? 'text-red-500' : 'text-purple-500'}
        subtext={`${status.memory_usage.toFixed(0)}%`}
        icon={Activity}
      />

      <div className="flex flex-col items-center justify-center p-2">
        <div className={`text-xl font-black font-mono mb-1 ${status.temperature > 75 ? 'text-red-500' : 'text-emerald-500'}`}>
          {status.temperature.toFixed(0)}°
        </div>
        <div className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center">
          <Thermometer className="w-3 h-3 mr-1" /> TEMP
        </div>
      </div>

      <div className="flex flex-col items-center justify-center p-2">
        <div className="text-lg font-bold font-mono text-foreground mb-1">
          {formatUptime(status.uptime).split(' ')[0]}
        </div>
        <div className="text-[10px] text-muted-foreground uppercase tracking-wider text-center">
          UPTIME
        </div>
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

        {/* --- Background Grid Lines (full page) --- */}
        <div className="absolute inset-0 z-0 opacity-[0.06] dark:opacity-[0.08] bg-[linear-gradient(to_right,currentColor_1px,transparent_1px),linear-gradient(to_bottom,currentColor_1px,transparent_1px)] bg-[size:3rem_3rem] pointer-events-none text-black dark:text-cyan-500" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[100vw] h-[500px] bg-primary/5 dark:bg-cyan-900/20 blur-[120px] rounded-full pointer-events-none" />


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

            {/* RIGHT: GPS & Signal Tracker & System Status */}
            <div className="lg:col-span-4 xl:col-span-3 flex flex-col space-y-4">

              {/* GPS & Signal Tracker Container - Side-by-side on desktop if space allows, or stacked */}
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 flex-1 min-h-0">
                {/* GPS Unit */}
                <div className="rounded-xl overflow-hidden border border-border bg-card/40 backdrop-blur-sm h-full min-h-[250px]">
                  <GPSCoordinateBox />
                </div>

                {/* Signal Tracker */}
                <div className="rounded-xl overflow-hidden border border-border bg-card/40 backdrop-blur-sm h-full min-h-[250px]">
                  <SignalTracker />
                </div>
              </div>

              {/* System Status Panel - Horizontal Compact */}
              <Card className="bg-card/80 dark:bg-[#0A0A0A]/80 border-border dark:border-white/10 backdrop-blur-sm rounded-xl overflow-hidden shadow-sm">
                <CardContent className="p-3">
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