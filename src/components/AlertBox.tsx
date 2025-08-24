import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useIsMobile } from '@/hooks/use-mobile';
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

export const AlertBox = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [expandedAlert, setExpandedAlert] = useState<string | null>(null);
  const isMobile = useIsMobile();

  // Simulate incoming alerts
  useEffect(() => {
    const sampleAlerts = [
      {
        type: 'warning' as const,
        title: 'High Temperature',
        message: isMobile ? 'Thermal sensor 42°C in zone A3' : 'Thermal sensor reading 42°C in zone A3'
      },
      {
        type: 'info' as const,
        title: 'GPS Update',
        message: isMobile ? 'Location updated' : 'Location updated to new coordinates'
      },
      {
        type: 'success' as const,
        title: 'System Online',
        message: isMobile ? 'All sensors operational' : 'All thermal sensors are operational'
      },
      {
        type: 'error' as const,
        title: 'Connection Lost',
        message: isMobile ? 'Lost connection to camera 2' : 'Lost connection to thermal camera 2'
      }
    ];

    // Add initial alerts
    const initialAlerts = sampleAlerts.map((alert, index) => ({
      id: `alert-${Date.now()}-${index}`,
      ...alert,
      timestamp: new Date(Date.now() - index * 60000),
      acknowledged: false
    }));

    setAlerts(initialAlerts);

    // Simulate new alerts coming in
    const interval = setInterval(() => {
      const randomAlert = sampleAlerts[Math.floor(Math.random() * sampleAlerts.length)];
      const newAlert: Alert = {
        id: `alert-${Date.now()}`,
        ...randomAlert,
        timestamp: new Date(),
        acknowledged: false
      };

      setAlerts(prev => [newAlert, ...prev].slice(0, 10)); // Keep only last 10 alerts
    }, 15000);

    return () => clearInterval(interval);
  }, [isMobile]);

  const acknowledgeAlert = (alertId: string) => {
    setAlerts(prev => prev.map(alert => 
      alert.id === alertId ? { ...alert, acknowledged: true } : alert
    ));
  };

  const dismissAlert = (alertId: string) => {
    setAlerts(prev => prev.filter(alert => alert.id !== alertId));
  };

  const toggleExpandAlert = (alertId: string) => {
    setExpandedAlert(expandedAlert === alertId ? null : alertId);
  };

  const getTimeAgo = (timestamp: Date) => {
    const now = new Date();
    const diff = now.getTime() - timestamp.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  const unacknowledgedCount = alerts.filter(alert => !alert.acknowledged).length;

  return (
    <Card className="h-full bg-dashboard-panel border-dashboard-panel-border">
      <CardHeader className="pb-3 sm:pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center text-base sm:text-lg">
            <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
            {isMobile ? 'Alerts' : 'System Alerts'}
          </CardTitle>
          {unacknowledgedCount > 0 && (
            <Badge variant="outline" className="bg-destructive/20 text-destructive border-destructive/30 text-xs sm:text-sm">
              {unacknowledgedCount} New
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex-1 p-0 overflow-hidden">
        <ScrollArea className={`h-full px-2 sm:px-4 ${isMobile ? 'max-h-[250px]' : 'max-h-[220px]'}`}>
          {alerts.length === 0 ? (
            <div className="text-center py-6 sm:py-8">
              <CheckCircle className="w-6 h-6 sm:w-8 sm:h-8 mx-auto text-success mb-2" />
              <p className="text-sm text-muted-foreground">No alerts</p>
              <p className="text-xs text-muted-foreground">All systems running normally</p>
            </div>
          ) : (
            <div className="space-y-2 sm:space-y-3 pb-4">
              {alerts.map((alert) => {
                const alertConfig = alertTypes[alert.type];
                const Icon = alertConfig.icon;
                const isExpanded = expandedAlert === alert.id;

                return (
                  <div
                    key={alert.id}
                    className={`
                      p-2 sm:p-3 rounded-lg border transition-all duration-200
                      ${alertConfig.bgColor} ${alertConfig.borderColor}
                      ${alert.acknowledged ? 'opacity-60' : 'opacity-100'}
                    `}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-2 flex-1">
                        <Icon className={`w-3 h-3 sm:w-4 sm:h-4 mt-0.5 ${alertConfig.textColor}`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              <h4 className={`text-xs sm:text-sm font-medium ${alertConfig.textColor}`}>
                                {alert.title}
                              </h4>
                              {alert.acknowledged && (
                                <Badge variant="outline" className="bg-success/20 text-success border-success/30 text-xs">
                                  ACK
                                </Badge>
                              )}
                            </div>
                            {isMobile && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => toggleExpandAlert(alert.id)}
                                className="h-6 w-6 p-0 ml-2"
                              >
                                {isExpanded ? (
                                  <ChevronUp className="w-3 h-3" />
                                ) : (
                                  <ChevronDown className="w-3 h-3" />
                                )}
                              </Button>
                            )}
                          </div>
                          
                          {/* Mobile: Collapsible message */}
                          {isMobile ? (
                            <>
                              {!isExpanded ? (
                                <p className="text-xs text-muted-foreground mt-1 truncate">
                                  {alert.message}
                                </p>
                              ) : (
                                <p className="text-xs text-muted-foreground mt-1">
                                  {alert.message}
                                </p>
                              )}
                            </>
                          ) : (
                            <p className="text-xs text-muted-foreground mt-1">
                              {alert.message}
                            </p>
                          )}
                          
                          <div className="flex items-center justify-between mt-2">
                            <div className="flex items-center space-x-1 text-xs text-muted-foreground">
                              <Clock className="w-2 h-2 sm:w-3 sm:h-3" />
                              <span>{getTimeAgo(alert.timestamp)}</span>
                            </div>
                            
                            {/* Mobile: Compact action buttons */}
                            <div className="flex items-center space-x-1">
                              {!alert.acknowledged && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => acknowledgeAlert(alert.id)}
                                  className="h-6 px-2 text-xs"
                                >
                                  ACK
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => dismissAlert(alert.id)}
                                className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
                              >
                                <X className="w-2 h-2 sm:w-3 sm:h-3" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};