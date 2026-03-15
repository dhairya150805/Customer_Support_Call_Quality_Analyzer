import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Phone, Loader2, CheckCircle2, MessageSquare, User, Clock, Zap, Upload } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface LiveCall {
  callId: string;
  agentId: string;
  agentName: string;
  duration: number;
  status: "active" | "analyzing" | "complete" | "failed";
  sentiment: string | null;
  score: number | null;
  lastMessage: string | null;
  lastSpeaker: string | null;
  startedAt: string | null;
  timeAgo: string;
  source: string;
}

function formatDuration(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function StatusBadge({ status }: { status: LiveCall["status"] }) {
  const map: Record<string, { label: string; cls: string; icon: JSX.Element }> = {
    active:    { label: "Live",       cls: "bg-success/10 text-success",      icon: <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" /> },
    analyzing: { label: "Analyzing",  cls: "bg-primary/10 text-primary",      icon: <Loader2 className="h-3 w-3 animate-spin" /> },
    complete:  { label: "Complete",   cls: "bg-muted text-muted-foreground",  icon: <CheckCircle2 className="h-3 w-3" /> },
    failed:    { label: "Failed",     cls: "bg-red-500/10 text-red-500",      icon: <span className="h-1.5 w-1.5 rounded-full bg-red-500" /> },
  };
  const s = map[status] || map.complete;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium ${s.cls}`}>
      {s.icon}
      {s.label}
    </span>
  );
}

function SentimentDot({ sentiment }: { sentiment: string | null }) {
  if (!sentiment) return null;
  const colors: Record<string, string> = {
    Positive: "bg-green-500",
    Neutral:  "bg-yellow-500",
    Negative: "bg-red-500",
  };
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
      <span className={`h-2 w-2 rounded-full ${colors[sentiment] || "bg-gray-400"}`} />
      {sentiment}
    </span>
  );
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return null;
  const cls = score >= 80 ? "text-green-500" : score >= 60 ? "text-yellow-500" : "text-red-500";
  return <span className={`text-xs font-bold tabular-nums ${cls}`}>{score}</span>;
}

function SourceIcon({ source }: { source: string }) {
  if (source === "live_session") return <Zap className="h-3 w-3 text-primary" />;
  return <Upload className="h-3 w-3 text-muted-foreground/60" />;
}

export function LiveCallMonitor() {
  const [calls, setCalls] = useState<LiveCall[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchCalls = () => {
    apiFetch<{ calls: LiveCall[] }>("/calls/live")
      .then((d) => setCalls(d.calls))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCalls();
    const interval = setInterval(fetchCalls, 5000);
    return () => clearInterval(interval);
  }, []);

  const activeCt = calls.filter((c) => c.status === "active").length;
  const analyzingCt = calls.filter((c) => c.status === "analyzing").length;

  return (
    <motion.div
      className="chart-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.4 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <Phone className="h-3.5 w-3.5" />
          Live Call Monitor
        </h3>
        <div className="flex items-center gap-3">
          {analyzingCt > 0 && (
            <span className="text-[10px] font-medium text-primary flex items-center gap-1">
              <Loader2 className="h-2.5 w-2.5 animate-spin" />
              {analyzingCt} analyzing
            </span>
          )}
          <span className="text-xs font-medium text-success flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
            {activeCt} active
          </span>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading calls…
        </div>
      ) : calls.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground text-sm">
          No calls yet. Upload calls or start a live session.
        </div>
      ) : (
        <div className="space-y-2">
          <AnimatePresence mode="popLayout">
            {calls.map((c) => (
              <motion.div
                key={c.callId}
                layout
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 8 }}
                transition={{ duration: 0.25 }}
                className={`rounded-lg border px-3 py-2.5 transition-colors ${
                  c.status === "active"
                    ? "border-success/30 bg-success/[0.03]"
                    : c.status === "analyzing"
                    ? "border-primary/30 bg-primary/[0.03]"
                    : "border-border bg-card"
                }`}
              >
                {/* Row 1: Call ID, Agent, Status, Score */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <SourceIcon source={c.source} />
                    <span className="text-sm font-medium tabular-nums truncate">{c.callId}</span>
                    <span className="text-[10px] text-muted-foreground">•</span>
                    <span className="text-xs text-muted-foreground truncate flex items-center gap-1">
                      <User className="h-3 w-3 shrink-0" />
                      {c.agentName || c.agentId}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <ScoreBadge score={c.score} />
                    <SentimentDot sentiment={c.sentiment} />
                    <StatusBadge status={c.status} />
                  </div>
                </div>

                {/* Row 2: Duration, Time ago, Last message */}
                <div className="flex items-center justify-between gap-2 mt-1.5">
                  <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1 tabular-nums">
                      <Clock className="h-3 w-3" />
                      {formatDuration(c.duration)}
                    </span>
                    <span>{c.timeAgo}</span>
                  </div>
                  {c.lastMessage && (
                    <div className="flex items-center gap-1 min-w-0 max-w-[60%]">
                      <MessageSquare className="h-3 w-3 text-muted-foreground/50 shrink-0" />
                      <span className="text-[11px] text-muted-foreground truncate">
                        {c.lastSpeaker && (
                          <span className="font-medium capitalize">{c.lastSpeaker}: </span>
                        )}
                        {c.lastMessage}
                      </span>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}
