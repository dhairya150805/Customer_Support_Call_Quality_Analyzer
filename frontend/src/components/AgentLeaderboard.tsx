import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Trophy, AlertCircle, ArrowUp, ArrowDown, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface AgentRanked {
  id: string;
  name: string;
  calls: number;
  score: number;
  rank?: number;
  trend_pct: number;
}

function getScoreColor(s: number) {
  if (s >= 90) return "text-success";
  if (s >= 70) return "text-warning";
  return "text-danger";
}

const medals = ["🥇", "🥈", "🥉"];

export function AgentLeaderboard({ filterParams = "" }: { filterParams?: string }) {
  const [top, setTop] = useState<AgentRanked[]>([]);
  const [needsImprovement, setNeedsImprovement] = useState<AgentRanked[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ top: AgentRanked[]; needs_improvement: AgentRanked[] }>(`/agents/leaderboard${filterParams ? "?" + filterParams : ""}`)
      .then((d) => {
        setTop(d.top);
        setNeedsImprovement(d.needs_improvement);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filterParams]);

  return (
    <motion.div
      className="chart-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.55 }}
    >
      <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-4">
        <Trophy className="h-3.5 w-3.5" />
        Agent Leaderboard
      </h3>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : (
        <>
          {/* Top Performers */}
          <div className="space-y-2 mb-5">
            {top.map((a, i) => (
              <motion.div
                key={a.id}
                className="flex items-center gap-3 p-2.5 rounded-lg bg-muted/30"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 + i * 0.04 }}
              >
                <span className="text-lg">{medals[i]}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">{a.name}</p>
                  <p className="text-xs text-muted-foreground">{a.id} · {a.calls} calls</p>
                </div>
                <span className={`text-sm font-bold tabular-nums ${getScoreColor(a.score)}`}>{a.score}</span>
                <span className="trend-up text-[10px]">
                  <ArrowUp className="h-3 w-3 inline" /> {a.trend_pct}%
                </span>
              </motion.div>
            ))}
          </div>

          {/* Needs Improvement */}
          <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-2">
            <AlertCircle className="h-3 w-3" />
            Needs Improvement
          </h4>
          <div className="space-y-2">
            {needsImprovement.map((a, i) => (
              <motion.div
                key={a.id}
                className="flex items-center gap-3 p-2.5 rounded-lg bg-danger/5 ring-1 ring-danger/10"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.7 + i * 0.04 }}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">{a.name}</p>
                  <p className="text-xs text-muted-foreground">{a.id} · {a.calls} calls</p>
                </div>
                <span className={`text-sm font-bold tabular-nums ${getScoreColor(a.score)}`}>{a.score}</span>
                <span className="trend-down text-[10px]">
                  <ArrowDown className="h-3 w-3 inline" /> {Math.abs(a.trend_pct)}%
                </span>
              </motion.div>
            ))}
          </div>
        </>
      )}
    </motion.div>
  );
}
