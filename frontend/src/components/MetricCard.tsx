import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string;
  trend: string;
  trendUp: boolean;
  icon: LucideIcon;
  index?: number;
}

export function MetricCard({ title, value, trend, trendUp, icon: Icon, index = 0 }: MetricCardProps) {
  return (
    <motion.div
      className="metric-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0, 0, 1], delay: index * 0.04 }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </span>
        <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
          <Icon className="h-4 w-4 text-primary" />
        </div>
      </div>
      <div className="text-2xl font-semibold tabular-nums text-foreground">{value}</div>
      <div className="mt-1">
        <span className={trendUp ? "trend-up" : "trend-down"}>
          {trendUp ? "↑" : "↓"} {trend}
        </span>
      </div>
    </motion.div>
  );
}
