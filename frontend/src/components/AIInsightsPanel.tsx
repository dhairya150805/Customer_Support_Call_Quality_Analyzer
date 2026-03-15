import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { BrainCircuit, TrendingUp, AlertTriangle, Zap, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Insight {
  icon: string;
  color: string;
  title: string;
  desc: string;
}

const iconComponents: Record<string, React.ElementType> = {
  TrendingUp, AlertTriangle, Zap, BrainCircuit,
};

export function AIInsightsPanel({ filterParams = "" }: { filterParams?: string }) {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ insights: Insight[] }>(`/ai-insights${filterParams ? "?" + filterParams : ""}`)
      .then((d) => setInsights(d.insights))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filterParams]);

  return (
    <motion.div
      className="chart-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.6 }}
    >
      <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-4">
        <BrainCircuit className="h-3.5 w-3.5" />
        AI-Generated Insights
      </h3>
      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm py-6 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : (
        <div className="space-y-3">
          {insights.map((ins, i) => {
            const Icon = iconComponents[ins.icon] ?? BrainCircuit;
            return (
              <motion.div
                key={i}
                className="flex items-start gap-3 p-3 rounded-lg bg-muted/20"
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.65 + i * 0.05 }}
              >
                <div className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${ins.color}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{ins.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{ins.desc}</p>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
