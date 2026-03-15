import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Flame, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

type HeatmapRow = {
  issue: string;
  mon: number; tue: number; wed: number; thu: number;
  fri: number; sat: number; sun: number;
};

const days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const dayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function getIntensity(value: number, max: number): string {
  const pct = value / max;
  if (pct >= 0.8) return "bg-danger/80 text-danger-foreground";
  if (pct >= 0.6) return "bg-warning/70 text-warning-foreground";
  if (pct >= 0.4) return "bg-warning/40 text-foreground";
  if (pct >= 0.2) return "bg-primary/20 text-foreground";
  return "bg-muted text-muted-foreground";
}

export function IssueHeatmap({ filterParams = "" }: { filterParams?: string }) {
  const [heatmapData, setHeatmapData] = useState<HeatmapRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ data: HeatmapRow[] }>(`/heatmap${filterParams ? "?" + filterParams : ""}`)
      .then((d) => setHeatmapData(d.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filterParams]);

  const maxVal = heatmapData.length > 0
    ? Math.max(...heatmapData.flatMap((d) => days.map((day) => d[day])))
    : 1;

  return (
    <motion.div
      className="chart-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.5 }}
    >
      <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-4">
        <Flame className="h-3.5 w-3.5" />
        Customer Issue Heatmap
      </h3>
      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium w-32">Issue</th>
                  {dayLabels.map((d) => (
                    <th key={d} className="text-center py-1.5 px-1 text-muted-foreground font-medium">{d}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {heatmapData.map((row, ri) => (
                  <tr key={row.issue}>
                    <td className="py-1 pr-3 text-foreground font-medium text-xs whitespace-nowrap">{row.issue}</td>
                    {days.map((day, di) => (
                      <td key={day} className="p-0.5">
                        <motion.div
                          className={`h-8 rounded flex items-center justify-center text-[10px] font-semibold tabular-nums ${getIntensity(row[day], maxVal)}`}
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ delay: 0.6 + ri * 0.03 + di * 0.02 }}
                        >
                          {row[day]}
                        </motion.div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-2 mt-3 text-[10px] text-muted-foreground">
            <span>Low</span>
            <div className="flex gap-0.5">
              <div className="h-3 w-6 rounded-sm bg-muted" />
              <div className="h-3 w-6 rounded-sm bg-primary/20" />
              <div className="h-3 w-6 rounded-sm bg-warning/40" />
              <div className="h-3 w-6 rounded-sm bg-warning/70" />
              <div className="h-3 w-6 rounded-sm bg-danger/80" />
            </div>
            <span>High</span>
          </div>
        </>
      )}
    </motion.div>
  );
}
