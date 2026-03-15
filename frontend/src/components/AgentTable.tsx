import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowUp, ArrowDown, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Agent {
  id: string;
  name: string;
  calls: number;
  score: number;
  sentiment: string;
  trend: string;
}

function getScoreClass(score: number) {
  if (score >= 90) return "score-green";
  if (score >= 70) return "score-yellow";
  return "score-red";
}

function getSentimentBadge(sentiment: string) {
  const classes: Record<string, string> = {
    Positive: "bg-[hsl(142,71%,45%,0.1)] text-[hsl(142,71%,45%)]",
    Neutral:  "bg-[hsl(38,92%,50%,0.1)] text-[hsl(38,92%,50%)]",
    Negative: "bg-[hsl(0,84%,60%,0.1)] text-[hsl(0,84%,60%)]",
  };
  return classes[sentiment] || "";
}

export function AgentTable({ filterParams = "" }: { filterParams?: string }) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ agents: Agent[] }>(`/agents${filterParams ? "?" + filterParams : ""}`)
      .then((d) => setAgents(d.agents))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filterParams]);

  return (
    <motion.div
      className="chart-card overflow-hidden"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0, 0, 1], delay: 0.35 }}
    >
      <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-4">
        Agent Performance
      </h3>
      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading agents…
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2.5 px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Agent ID</th>
                <th className="text-left py-2.5 px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Name</th>
                <th className="text-left py-2.5 px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Calls</th>
                <th className="text-left py-2.5 px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Avg Score</th>
                <th className="text-left py-2.5 px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Sentiment</th>
                <th className="text-left py-2.5 px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Trend</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent, idx) => (
                <tr key={`${agent.id}-${idx}`} className="border-b border-border/50 hover:bg-muted/40 transition-colors cursor-pointer">
                  <td className="py-3 px-3 font-medium tabular-nums">{agent.id}</td>
                  <td className="py-3 px-3">{agent.name}</td>
                  <td className="py-3 px-3 tabular-nums">{agent.calls}</td>
                  <td className={`py-3 px-3 font-semibold tabular-nums ${getScoreClass(agent.score)}`}>{agent.score}</td>
                  <td className="py-3 px-3">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${getSentimentBadge(agent.sentiment)}`}>
                      {agent.sentiment}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    {agent.trend === "up" ? (
                      <ArrowUp className="h-4 w-4 text-success" />
                    ) : (
                      <ArrowDown className="h-4 w-4 text-danger" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  );
}
