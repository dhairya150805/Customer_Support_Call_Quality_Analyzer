import { useEffect, useState } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { motion, AnimatePresence } from "framer-motion";
import {
  Phone, Loader2, CheckCircle2, Clock, User, MessageSquare,
  Activity, ThumbsUp, ThumbsDown, AlertTriangle, Smile, Frown,
  Meh, Tag, ChevronRight, ArrowLeft, Zap, ShieldCheck
} from "lucide-react";
import { apiFetch } from "@/lib/api";

/* ── Types ──────────────────────────────────────────────────────────────── */

interface TranscriptMsg {
  seq: number;
  speaker: string;
  text: string;
}

interface Analysis {
  sentiment: string | null;
  emotion: string | null;
  summary: string | null;
  issue: string | null;
  resolutionStatus: string | null;
  score: number | null;
  agentProfessionalism: number | null;
  customerFrustration: number | null;
  communicationScore: number | null;
  problemSolvingScore: number | null;
  empathyScore: number | null;
  complianceScore: number | null;
  closingScore: number | null;
}

interface LiveCall {
  sessionId: number;
  callId: number | null;
  contactId: string;
  agentName: string;
  phone: string | null;
  status: string;
  startedAt: string | null;
  endedAt: string | null;
  durationSec: number;
  timeAgo: string;
  transcript: TranscriptMsg[];
  analysis: Analysis | null;
  tags: string[];
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function formatDuration(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function SentimentIcon({ sentiment }: { sentiment: string | null }) {
  if (!sentiment) return <Meh className="h-4 w-4 text-muted-foreground" />;
  if (sentiment === "Positive") return <Smile className="h-4 w-4 text-green-500" />;
  if (sentiment === "Negative") return <Frown className="h-4 w-4 text-red-500" />;
  return <Meh className="h-4 w-4 text-yellow-500" />;
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string; icon: JSX.Element }> = {
    active:    { label: "Live",      cls: "bg-green-500/10 text-green-500",          icon: <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" /> },
    analyzing: { label: "Analyzing", cls: "bg-blue-500/10 text-blue-500",            icon: <Loader2 className="h-3 w-3 animate-spin" /> },
    complete:  { label: "Complete",  cls: "bg-muted text-muted-foreground",          icon: <CheckCircle2 className="h-3 w-3" /> },
    failed:    { label: "Failed",    cls: "bg-red-500/10 text-red-500",              icon: <span className="h-1.5 w-1.5 rounded-full bg-red-500" /> },
  };
  const s = map[status] || map.complete;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${s.cls}`}>
      {s.icon} {s.label}
    </span>
  );
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? "text-green-500" : score >= 60 ? "text-yellow-500" : "text-red-500";
  const bg = score >= 80 ? "stroke-green-500" : score >= 60 ? "stroke-yellow-500" : "stroke-red-500";
  const pct = score / 100;
  const r = 28;
  const circ = 2 * Math.PI * r;
  const offset = circ - pct * circ;
  return (
    <div className="relative w-16 h-16">
      <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r={r} fill="none" stroke="currentColor" className="text-muted/30" strokeWidth="4" />
        <motion.circle
          cx="32" cy="32" r={r} fill="none" className={bg} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.8, ease: [0.34, 1.56, 0.64, 1] }}
        />
      </svg>
      <span className={`absolute inset-0 flex items-center justify-center text-sm font-bold tabular-nums ${color}`}>
        {score}
      </span>
    </div>
  );
}

function ScoreBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = (score / max) * 100;
  const color = pct >= 80 ? "bg-green-500" : pct >= 60 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">{score}/{max}</span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${color}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: [0.34, 1.56, 0.64, 1], delay: 0.2 }}
        />
      </div>
    </div>
  );
}

function RatingDots({ value, max = 5, color }: { value: number; max?: number; color: string }) {
  return (
    <div className="flex gap-1">
      {Array.from({ length: max }).map((_, i) => (
        <span key={i} className={`h-2 w-2 rounded-full ${i < value ? color : "bg-muted"}`} />
      ))}
    </div>
  );
}

/* ── Call List Item ─────────────────────────────────────────────────────── */

function CallCard({ call, onClick }: { call: LiveCall; onClick: () => void }) {
  const a = call.analysis;
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-xl border p-4 cursor-pointer transition-all hover:shadow-md hover:border-primary/30 ${
        call.status === "active" ? "border-green-500/30 bg-green-500/[0.02]" :
        call.status === "analyzing" ? "border-blue-500/30 bg-blue-500/[0.02]" :
        "border-border bg-card"
      }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Phone className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">{call.agentName}</span>
          {call.phone && <span className="text-xs text-muted-foreground">{call.phone}</span>}
        </div>
        <div className="flex items-center gap-2">
          {a?.score != null && <ScoreRing score={a.score} />}
          <StatusBadge status={call.status} />
        </div>
      </div>
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {formatDuration(call.durationSec)}</span>
        <span>{call.timeAgo}</span>
        <span className="flex items-center gap-1"><MessageSquare className="h-3 w-3" /> {call.transcript.length} turns</span>
        {a?.sentiment && (
          <span className="flex items-center gap-1">
            <SentimentIcon sentiment={a.sentiment} />
            {a.sentiment}
          </span>
        )}
      </div>
      {a?.summary && (
        <p className="text-xs text-muted-foreground mt-2 line-clamp-2">{a.summary}</p>
      )}
      {call.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {call.tags.slice(0, 5).map((t, i) => (
            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/5 text-[10px] font-medium text-primary">
              <Tag className="h-2.5 w-2.5" />{t}
            </span>
          ))}
        </div>
      )}
      <div className="flex items-center justify-end mt-2">
        <span className="text-[10px] text-muted-foreground flex items-center gap-1">
          View details <ChevronRight className="h-3 w-3" />
        </span>
      </div>
    </motion.div>
  );
}

/* ── Call Detail View ──────────────────────────────────────────────────── */

function CallDetail({ call, onBack }: { call: LiveCall; onBack: () => void }) {
  const a = call.analysis;

  const scoreBreakdown = a ? [
    { label: "Communication", score: a.communicationScore ?? 0, max: 30 },
    { label: "Problem Solving", score: a.problemSolvingScore ?? 0, max: 25 },
    { label: "Empathy", score: a.empathyScore ?? 0, max: 20 },
    { label: "Compliance", score: a.complianceScore ?? 0, max: 15 },
    { label: "Closing", score: a.closingScore ?? 0, max: 10 },
  ] : [];

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      {/* Back button */}
      <button onClick={onBack} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4 transition-colors">
        <ArrowLeft className="h-4 w-4" /> Back to calls
      </button>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Zap className="h-5 w-5 text-primary" />
            {call.agentName}
            <StatusBadge status={call.status} />
          </h2>
          <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
            {call.phone && <span>{call.phone}</span>}
            <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {formatDuration(call.durationSec)}</span>
            <span>{call.timeAgo}</span>
            <span>Session #{call.sessionId}</span>
          </div>
        </div>
        {a?.score != null && <ScoreRing score={a.score} />}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* LEFT: Transcript */}
        <motion.div
          className="lg:col-span-1 chart-card bg-muted/30"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
        >
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
            <MessageSquare className="h-3.5 w-3.5" /> Live Transcript
          </h3>
          <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
            {call.transcript.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">No transcript available</p>
            ) : (
              call.transcript.map((msg) => (
                <div
                  key={msg.seq}
                  className={`p-3 rounded-lg text-sm ${
                    msg.speaker === "agent"
                      ? "bg-primary/5 ring-1 ring-primary/10 ml-4"
                      : msg.speaker === "customer"
                      ? "bg-card ring-1 ring-border mr-4"
                      : "bg-muted/50 ring-1 ring-border"
                  }`}
                >
                  <span className={`text-[10px] font-semibold uppercase tracking-wider ${
                    msg.speaker === "agent" ? "text-primary" : "text-muted-foreground"
                  }`}>
                    {msg.speaker === "agent" ? "🤖 Agent" : msg.speaker === "customer" ? "👤 Customer" : msg.speaker}
                  </span>
                  <p className="mt-1 text-foreground leading-relaxed">{msg.text}</p>
                </div>
              ))
            )}
          </div>
        </motion.div>

        {/* CENTER: Sentiment & Analysis */}
        <motion.div
          className="lg:col-span-1 chart-card"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.05 }}
        >
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
            <Activity className="h-3.5 w-3.5" /> Sentiment & Analysis
          </h3>

          {!a ? (
            <div className="py-12 text-center text-muted-foreground">
              {call.status === "analyzing" ? (
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  <p className="text-sm">Analysis in progress…</p>
                </div>
              ) : (
                <p className="text-sm">No analysis available yet</p>
              )}
            </div>
          ) : (
            <div className="space-y-5">
              {/* Sentiment */}
              <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
                <SentimentIcon sentiment={a.sentiment} />
                <div>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">Sentiment</span>
                  <p className={`text-sm font-semibold ${
                    a.sentiment === "Positive" ? "text-green-500" :
                    a.sentiment === "Negative" ? "text-red-500" : "text-yellow-500"
                  }`}>{a.sentiment || "Unknown"}</p>
                </div>
              </div>

              {/* Emotion */}
              {a.emotion && (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
                  <Smile className="h-4 w-4 text-primary" />
                  <div>
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">Emotion</span>
                    <p className="text-sm font-semibold">{a.emotion}</p>
                  </div>
                </div>
              )}

              {/* Summary */}
              {a.summary && (
                <div className="border-l-2 border-primary pl-3">
                  <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Summary</span>
                  <p className="text-sm text-foreground mt-1">{a.summary}</p>
                </div>
              )}

              {/* Issue & Resolution */}
              <div className="grid grid-cols-2 gap-3">
                {a.issue && (
                  <div className="p-3 rounded-lg bg-muted/30">
                    <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Issue</span>
                    <p className="text-xs font-medium mt-0.5">{a.issue}</p>
                  </div>
                )}
                {a.resolutionStatus && (
                  <div className="p-3 rounded-lg bg-muted/30">
                    <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Resolution</span>
                    <p className={`text-xs font-medium mt-0.5 ${
                      a.resolutionStatus === "Resolved" ? "text-green-500" :
                      a.resolutionStatus === "Not Resolved" ? "text-red-500" : "text-yellow-500"
                    }`}>{a.resolutionStatus}</p>
                  </div>
                )}
              </div>

              {/* Agent Professionalism & Customer Frustration */}
              <div className="space-y-3 pt-2">
                {a.agentProfessionalism != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <ThumbsUp className="h-3 w-3" /> Agent Professionalism
                    </span>
                    <RatingDots value={a.agentProfessionalism} color="bg-green-500" />
                  </div>
                )}
                {a.customerFrustration != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <AlertTriangle className="h-3 w-3" /> Customer Frustration
                    </span>
                    <RatingDots value={a.customerFrustration} color="bg-red-500" />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tags */}
          {call.tags.length > 0 && (
            <div className="mt-5 pt-4 border-t border-border">
              <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 mb-2">
                <Tag className="h-3 w-3" /> Tags
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {call.tags.map((t, i) => (
                  <span key={i} className="px-2 py-0.5 rounded-full bg-primary/10 text-[10px] font-medium text-primary">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
        </motion.div>

        {/* RIGHT: Quality Scores */}
        <motion.div
          className="lg:col-span-1 chart-card"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}
        >
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
            <ShieldCheck className="h-3.5 w-3.5" /> Quality Scores
          </h3>

          {!a || a.score == null ? (
            <div className="py-12 text-center text-muted-foreground">
              <p className="text-sm">Scores not available</p>
            </div>
          ) : (
            <>
              <div className="flex justify-center mb-6">
                <ScoreRing score={a.score} />
              </div>
              <div className="space-y-4">
                {scoreBreakdown.map((item) => (
                  <ScoreBar key={item.label} {...item} />
                ))}
              </div>
            </>
          )}
        </motion.div>
      </div>
    </motion.div>
  );
}

/* ── Main Page ─────────────────────────────────────────────────────────── */


const LiveTranscriptAnalyzer = () => {
  const [calls, setCalls] = useState<LiveCall[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<LiveCall | null>(null);
  const [simLoading, setSimLoading] = useState(false);

  async function simulateCall() {
    setSimLoading(true);
    try {
      await apiFetch("/calls/simulate", { method: "POST" });
      // Refresh data after simulation
      const d = await apiFetch<{ calls: LiveCall[] }>("/calls/live-analysis");
      setCalls(d.calls);
    } catch (e) {
      alert("Simulation failed: " + e);
    } finally {
      setSimLoading(false);
    }
  }

  useEffect(() => {
    const fetchCalls = () => {
      apiFetch<{ calls: LiveCall[] }>("/calls/live-analysis")
        .then((d) => {
          setCalls(d.calls);
          setSelected((prev) => {
            if (!prev) return null;
            return d.calls.find((c) => c.sessionId === prev.sessionId) ?? prev;
          });
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    };

    fetchCalls();
    const interval = setInterval(fetchCalls, 8000);
    return () => clearInterval(interval);
  }, []);

  const activeCt = calls.filter((c) => c.status === "active").length;
  const analyzingCt = calls.filter((c) => c.status === "analyzing").length;
  const completeCt = calls.filter((c) => c.status === "complete").length;

  return (
    <DashboardLayout>
      <div className="mb-6 flex items-center gap-4">
        <h1 className="text-[28px] font-semibold text-foreground tracking-tight flex items-center gap-3">
          <Phone className="h-7 w-7 text-primary" />
          Live Transcript Analyzer
        </h1>
        <button
          onClick={simulateCall}
          disabled={simLoading}
          className="px-4 py-1.5 rounded-lg bg-primary text-white font-medium text-sm shadow hover:bg-primary/90 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {simLoading ? "Simulating..." : "Simulate Call"}
        </button>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-6 mb-5">
        <span className="flex items-center gap-1.5 text-xs font-medium">
          <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          {activeCt} Live
        </span>
        <span className="flex items-center gap-1.5 text-xs font-medium text-blue-500">
          <Loader2 className="h-3 w-3 animate-spin" />
          {analyzingCt} Analyzing
        </span>
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <CheckCircle2 className="h-3 w-3" />
          {completeCt} Complete
        </span>
        <span className="text-xs text-muted-foreground ml-auto">
          Auto-refreshes every 8s
        </span>
      </div>

      {selected ? (
        <CallDetail call={selected} onBack={() => setSelected(null)} />
      ) : loading ? (
        <div className="flex items-center gap-2 text-muted-foreground py-24 justify-center">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading live calls…
        </div>
      ) : calls.length === 0 ? (
        <div className="p-10 rounded-2xl border-2 border-dashed border-border bg-muted/20 flex flex-col items-center text-center gap-4">
          <div className="h-14 w-14 rounded-2xl bg-primary/10 flex items-center justify-center">
            <Phone className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">No live calls yet</h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              Call <strong>+1 (862) 225-2211</strong> to start a conversation with the AI agent.
              Transcripts and analysis will appear here in real-time.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <AnimatePresence mode="popLayout">
            {calls.map((c) => (
              <CallCard key={c.sessionId} call={c} onClick={() => setSelected(c)} />
            ))}
          </AnimatePresence>
        </div>
      )}
    </DashboardLayout>
  );
};

export default LiveTranscriptAnalyzer;
