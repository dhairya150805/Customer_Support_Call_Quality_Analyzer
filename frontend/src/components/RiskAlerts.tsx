import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Angry, Timer, XCircle, TrendingDown, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface RiskAlert {
  id: string;
  type: "angry" | "lowScore" | "silence" | "unresolved";
  callId: string;
  agentId: string;
  message: string;
  time: string;
}

const iconMap = {
  angry:      Angry,
  lowScore:   TrendingDown,
  silence:    Timer,
  unresolved: XCircle,
};

const colorMap = {
  angry:      "text-danger bg-danger/10 ring-danger/20",
  lowScore:   "text-warning bg-warning/10 ring-warning/20",
  silence:    "text-primary bg-primary/10 ring-primary/20",
  unresolved: "text-danger bg-danger/10 ring-danger/20",
};

export function RiskAlerts({ filterParams = "" }: { filterParams?: string }) {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ alerts: RiskAlert[] }>(`/calls/risk-alerts${filterParams ? "?" + filterParams : ""}`)
      .then((d) => setAlerts(d.alerts))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filterParams]);

  return (
    <motion.div
      className="chart-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.45 }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5" />
          AI Risk Detection
        </h3>
        <span className="text-xs font-medium text-danger">{alerts.length} alerts</span>
      </div>
      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm py-6 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : (
        <div className="space-y-2.5">
          {alerts.map((alert, i) => {
            const Icon = iconMap[alert.type];
            return (
              <motion.div
                key={alert.id}
                className={`flex items-start gap-3 p-3 rounded-lg ring-1 ${colorMap[alert.type]}`}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5 + i * 0.05 }}
              >
                <Icon className="h-4 w-4 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{alert.message}</p>
                  <p className="text-xs opacity-70 mt-0.5">
                    {alert.callId} · {alert.agentId} · {alert.time}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
