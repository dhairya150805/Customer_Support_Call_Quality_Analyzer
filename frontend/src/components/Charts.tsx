import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import { Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

function ChartWrapper({ title, children, index = 0 }: { title: string; children: React.ReactNode; index?: number }) {
  return (
    <motion.div
      className="chart-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0, 0, 1], delay: 0.2 + index * 0.04 }}
    >
      <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-4">{title}</h3>
      {children}
    </motion.div>
  );
}

function LoadingChart() {
  return (
    <div className="flex items-center gap-2 text-muted-foreground text-sm h-[220px] justify-center">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading…
    </div>
  );
}

function EmptyChart() {
  return (
    <div className="flex items-center text-muted-foreground text-sm h-[220px] justify-center">
      No data available
    </div>
  );
}

export function TopIssuesChart({ filterParams = "" }: { filterParams?: string }) {
  const [data, setData] = useState<{ issue: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    apiFetch<{ data: typeof data }>(`/charts/top-issues${filterParams ? "?" + filterParams : ""}`).then((d) => setData(d.data)).catch(console.error).finally(() => setLoading(false));
  }, [filterParams]);
  return (
    <ChartWrapper title="Top Customer Issues" index={0}>
      {loading ? <LoadingChart /> : data.length === 0 ? <EmptyChart /> : (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} layout="vertical" margin={{ left: 10 }}>
            <XAxis type="number" hide />
            <YAxis dataKey="issue" type="category" width={110} tick={{ fontSize: 12, fill: "hsl(215, 16%, 47%)" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid hsl(214, 32%, 91%)", fontSize: 12 }} />
            <Bar dataKey="count" fill="hsl(243, 75%, 59%)" radius={[0, 6, 6, 0]} barSize={20} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartWrapper>
  );
}

export function SentimentChart({ filterParams = "" }: { filterParams?: string }) {
  const [data, setData] = useState<{ name: string; value: number; color: string }[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    apiFetch<{ data: typeof data }>(`/charts/sentiment${filterParams ? "?" + filterParams : ""}`).then((d) => setData(d.data)).catch(console.error).finally(() => setLoading(false));
  }, [filterParams]);
  return (
    <ChartWrapper title="Customer Sentiment" index={1}>
      {loading ? <LoadingChart /> : data.length === 0 ? <EmptyChart /> : (
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={4} dataKey="value" stroke="none">
              {data.map((entry, i) => (<Cell key={i} fill={entry.color} />))}
            </Pie>
            <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid hsl(214, 32%, 91%)", fontSize: 12 }} />
            <Legend verticalAlign="bottom" iconType="circle" iconSize={8}
              formatter={(value: string) => <span className="text-xs text-muted-foreground ml-1">{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </ChartWrapper>
  );
}

export function QualityTrendChart({ filterParams = "" }: { filterParams?: string }) {
  const [data, setData] = useState<{ week: string; score: number }[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    apiFetch<{ data: typeof data }>(`/charts/quality-trend${filterParams ? "?" + filterParams : ""}`).then((d) => setData(d.data)).catch(console.error).finally(() => setLoading(false));
  }, [filterParams]);
  return (
    <ChartWrapper title="Quality Score Over Time" index={2}>
      {loading ? <LoadingChart /> : data.length === 0 ? <EmptyChart /> : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(214, 32%, 91%)" />
            <XAxis dataKey="week" tick={{ fontSize: 12, fill: "hsl(215, 16%, 47%)" }} axisLine={false} tickLine={false} />
            <YAxis domain={[60, 100]} tick={{ fontSize: 12, fill: "hsl(215, 16%, 47%)" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid hsl(214, 32%, 91%)", fontSize: 12 }} />
            <Line type="monotone" dataKey="score" stroke="hsl(243, 75%, 59%)" strokeWidth={2.5}
              dot={{ r: 4, fill: "hsl(243, 75%, 59%)", stroke: "white", strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartWrapper>
  );
}

export function AgentScoreDistChart({ filterParams = "" }: { filterParams?: string }) {
  const [data, setData] = useState<{ range: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    apiFetch<{ data: typeof data }>(`/charts/agent-score-dist${filterParams ? "?" + filterParams : ""}`).then((d) => setData(d.data)).catch(console.error).finally(() => setLoading(false));
  }, [filterParams]);
  return (
    <ChartWrapper title="Agent Score Distribution" index={3}>
      {loading ? <LoadingChart /> : data.length === 0 ? <EmptyChart /> : (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data}>
            <XAxis dataKey="range" tick={{ fontSize: 11, fill: "hsl(215, 16%, 47%)" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 12, fill: "hsl(215, 16%, 47%)" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid hsl(214, 32%, 91%)", fontSize: 12 }} />
            <Bar dataKey="count" fill="hsl(243, 75%, 59%)" radius={[6, 6, 0, 0]} barSize={32} opacity={0.85} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartWrapper>
  );
}
