import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { FileText, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Summary {
  callId: string;
  agent: string;
  score: number;
  summary: string;
  time: string;
}

function getScoreColor(s: number) {
  if (s >= 90) return "text-success bg-success/10";
  if (s >= 70) return "text-warning bg-warning/10";
  return "text-danger bg-danger/10";
}

export function RecentSummaries({ filterParams = "" }: { filterParams?: string }) {
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ summaries: Summary[] }>(`/calls/recent-summaries${filterParams ? "?" + filterParams : ""}`)
      .then((d) => setSummaries(d.summaries))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filterParams]);

  return (
    <motion.div
      className="chart-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.5 }}
    >
      <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-4">
        <FileText className="h-3.5 w-3.5" />
        Recent AI Call Summaries
      </h3>
      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm py-6 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : (
        <div className="space-y-3">
          {summaries.map((s, i) => (
            <motion.div
              key={s.callId + i}
              className="p-3 rounded-lg bg-muted/30 ring-1 ring-border/50"
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.55 + i * 0.04 }}
            >
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold tabular-nums text-foreground">{s.callId}</span>
                  <span className="text-xs text-muted-foreground">· {s.agent}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold tabular-nums px-1.5 py-0.5 rounded ${getScoreColor(s.score)}`}>{s.score}</span>
                  <span className="text-xs text-muted-foreground">{s.time}</span>
                </div>
              </div>
              <p className="text-sm text-foreground/80 leading-relaxed">{s.summary}</p>
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
