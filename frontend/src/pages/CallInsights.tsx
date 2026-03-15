import { useEffect, useState } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { motion } from "framer-motion";
import { Shield, ThumbsUp, MessageSquare, Target, Lightbulb, TrendingUp, AlertCircle, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

const highlightStyles: Record<string, { bg: string; label: string; icon: React.ReactNode }> = {
  complaint:   { bg: "ring-danger/30 bg-danger/5",   label: "Customer Complaint",    icon: <AlertCircle className="h-3 w-3 text-danger" /> },
  empathy:     { bg: "ring-primary/30 bg-primary/5", label: "Agent Empathy",         icon: <ThumbsUp className="h-3 w-3 text-primary" /> },
  resolution:  { bg: "ring-success/30 bg-success/5", label: "Resolution Confirmed",  icon: <Target className="h-3 w-3 text-success" /> },
};

interface TranscriptLine {
  speaker: string;
  text: string;
  highlight: string | null;
}

interface ScoreItem {
  label: string;
  score: number;
  max: number;
}

interface ConfidenceItem {
  label: string;
  confidence: number;
}

interface CallData {
  empty?: boolean;
  transcript: TranscriptLine[];
  insights: Record<string, string>;
  score_breakdown: ScoreItem[];
  coaching: { strengths: string[]; improvements: string[] };
  confidence: ConfidenceItem[];
  quality_score: number;
  tags?: string[];
}

function ScoreGauge({ score, max }: { score: number; max: number }) {
  const pct = (score / max) * 100;
  const radius = 60;
  const circumference = Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const color = pct >= 90 ? "hsl(142,71%,45%)" : pct >= 70 ? "hsl(38,92%,50%)" : "hsl(0,84%,60%)";
  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="80" viewBox="0 0 140 80">
        <path d="M 10 75 A 60 60 0 0 1 130 75" fill="none" stroke="hsl(214, 32%, 91%)" strokeWidth="8" strokeLinecap="round" />
        <motion.path
          d="M 10 75 A 60 60 0 0 1 130 75"
          fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.8, ease: [0.34, 1.56, 0.64, 1] }}
        />
      </svg>
      <div className="text-2xl font-semibold tabular-nums -mt-3" style={{ color }}>{score}/{max}</div>
    </div>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  const color = value >= 90 ? "text-success bg-success/10" : value >= 75 ? "text-warning bg-warning/10" : "text-danger bg-danger/10";
  return <span className={`text-[10px] font-bold tabular-nums px-1.5 py-0.5 rounded ${color}`}>{value}%</span>;
}

const CallInsights = () => {
  const [data, setData] = useState<CallData | null>(null);
  const [loading, setLoading] = useState(true);
  const [simLoading, setSimLoading] = useState(false);

  async function simulateCall() {
    setSimLoading(true);
    try {
      await apiFetch("/calls/simulate", { method: "POST" });
      // Refresh data after simulation
      const d = await apiFetch<CallData>("/calls/last-insight");
      setData(d);
    } catch (e) {
      alert("Simulation failed: " + e);
    } finally {
      setSimLoading(false);
    }
  }

  useEffect(() => {
    apiFetch<CallData>("/calls/last-insight")
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center gap-2 text-muted-foreground py-24 justify-center">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading call data…
        </div>
      </DashboardLayout>
    );
  }

  if (!data) return null;

  if (data.empty) {
    return (
      <DashboardLayout>
        <div className="mb-6">
          <h1 className="text-[28px] font-semibold text-foreground tracking-tight">Call Insights</h1>
          <p className="text-sm text-muted-foreground mt-1">AI-powered call analysis and quality scoring</p>
        </div>
        <div className="p-10 rounded-2xl border-2 border-dashed border-border bg-muted/20 flex flex-col items-center text-center gap-4">
          <div className="h-14 w-14 rounded-2xl bg-primary/10 flex items-center justify-center">
            <MessageSquare className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">No call data yet</h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              Upload call transcripts to see AI-powered insights, quality scoring, and coaching recommendations here.
            </p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const totalScore = data.score_breakdown.reduce((a, b) => a + b.score, 0);
  const totalMax   = data.score_breakdown.reduce((a, b) => a + b.max,   0);

  return (
    <DashboardLayout>
      <div className="mb-6 flex items-center gap-4">
        <h1 className="text-[28px] font-semibold text-foreground tracking-tight">Call Insights</h1>
        <button
          onClick={simulateCall}
          disabled={simLoading}
          className="px-4 py-1.5 rounded-lg bg-primary text-white font-medium text-sm shadow hover:bg-primary/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {simLoading ? "Simulating..." : "Simulate Call"}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Transcript */}
        <motion.div className="lg:col-span-1 chart-card bg-muted/30" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">Transcript</h3>
          <div className="flex flex-wrap gap-2 mb-3">
            {Object.entries(highlightStyles).map(([key, style]) => (
              <span key={key} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full ring-1 text-[10px] font-medium ${style.bg}`}>
                {style.icon} {style.label}
              </span>
            ))}
          </div>
          <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
            {data.transcript.map((msg, i) => {
              const hl = msg.highlight ? highlightStyles[msg.highlight] : null;
              return (
                <div key={i} className={`p-3 rounded-lg text-sm ${msg.speaker === "Agent" ? "bg-card ring-1 ring-border" : ""} ${hl ? `ring-1 ${hl.bg}` : ""}`}>
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium text-muted-foreground">{msg.speaker}</span>
                    {hl && <span className="inline-flex items-center gap-1 text-[10px] font-medium">{hl.icon} {hl.label}</span>}
                  </div>
                  <p className="mt-1 text-foreground">{msg.text}</p>
                </div>
              );
            })}
          </div>
        </motion.div>

        {/* AI Insights */}
        <motion.div className="lg:col-span-1 chart-card" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.05 }}>
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-4">AI Insights</h3>
          <div className="space-y-4">
            {Object.entries(data.insights).map(([key, value]) => (
              <div key={key} className="border-l-2 border-primary pl-3">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{key}</span>
                <p className="text-sm text-foreground mt-0.5">{value}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 pt-4 border-t border-border">
            <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 mb-3">
              <Shield className="h-3 w-3" /> AI Confidence Scores
            </h4>
            <div className="space-y-2">
              {data.confidence.map((m) => (
                <div key={m.label} className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{m.label}</span>
                  <ConfidenceBadge value={m.confidence} />
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Quality Score */}
        <motion.div className="lg:col-span-1 chart-card" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}>
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-4">Quality Score</h3>
          <ScoreGauge score={totalScore} max={totalMax} />
          <div className="mt-5 space-y-3">
            {data.score_breakdown.map((item) => {
              const pct = (item.score / item.max) * 100;
              return (
                <div key={item.label}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="font-medium tabular-nums text-foreground">{item.score}/{item.max}</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ backgroundColor: pct >= 90 ? "hsl(142,71%,45%)" : pct >= 70 ? "hsl(38,92%,50%)" : "hsl(0,84%,60%)" }}
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.8, ease: [0.34, 1.56, 0.64, 1], delay: 0.3 }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>
      </div>

      {/* Coaching */}
      <motion.div className="chart-card mt-5" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.15 }}>
        <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-4">
          <Lightbulb className="h-3.5 w-3.5" />
          AI Agent Coaching
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <h4 className="text-xs font-medium text-success flex items-center gap-1.5 mb-3">
              <ThumbsUp className="h-3.5 w-3.5" /> Strengths
            </h4>
            <div className="space-y-2">
              {data.coaching.strengths.map((s, i) => (
                <motion.div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-success/5 ring-1 ring-success/10"
                  initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + i * 0.05 }}>
                  <div className="h-1.5 w-1.5 rounded-full bg-success mt-1.5 shrink-0" />
                  <p className="text-sm text-foreground">{s}</p>
                </motion.div>
              ))}
            </div>
          </div>
          <div>
            <h4 className="text-xs font-medium text-warning flex items-center gap-1.5 mb-3">
              <TrendingUp className="h-3.5 w-3.5" /> Areas for Improvement
            </h4>
            <div className="space-y-2">
              {data.coaching.improvements.map((s, i) => (
                <motion.div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-warning/5 ring-1 ring-warning/10"
                  initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + i * 0.05 }}>
                  <div className="h-1.5 w-1.5 rounded-full bg-warning mt-1.5 shrink-0" />
                  <p className="text-sm text-foreground">{s}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Tags */}
      {data.tags && data.tags.length > 0 && (
        <motion.div className="chart-card mt-5" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }}>
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">Call Tags</h3>
          <div className="flex flex-wrap gap-2">
            {data.tags.map((tag, i) => (
              <span key={i} className="px-3 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary ring-1 ring-primary/20">
                {tag.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </motion.div>
      )}
      <button
        className="mt-5 flex items-center gap-2 text-sm font-medium text-primary"
        onClick={simulateCall}
        disabled={simLoading}
      >
        {simLoading ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : (
          <span>Simulate Call</span>
        )}
      </button>
    </DashboardLayout>
  );
};

export default CallInsights;
