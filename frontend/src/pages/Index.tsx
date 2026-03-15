import { useCallback, useEffect, useMemo, useState } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { MetricCard } from "@/components/MetricCard";
import { TopIssuesChart, SentimentChart, QualityTrendChart, AgentScoreDistChart } from "@/components/Charts";
import { AgentTable } from "@/components/AgentTable";
import { LiveCallMonitor } from "@/components/LiveCallMonitor";
import { RiskAlerts } from "@/components/RiskAlerts";
import { RecentSummaries } from "@/components/RecentSummaries";
import { AgentLeaderboard } from "@/components/AgentLeaderboard";
import { AIInsightsPanel } from "@/components/AIInsightsPanel";
import { IssueHeatmap } from "@/components/IssueHeatmap";
import { DashboardFilters, FilterState } from "@/components/DashboardFilters";
import { ExportReports } from "@/components/ExportReports";
import { DemoDataGenerator } from "@/components/DemoDataGenerator";
import { Phone, TrendingUp, CheckCircle, AlertTriangle, Upload, ArrowRight } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useNavigate } from "react-router-dom";

const icons = [Phone, TrendingUp, CheckCircle, AlertTriangle];

const emptyFilters: FilterState = {
  agent: "", issue: "", sentiment: "", duration: "", dateFrom: "", dateTo: "", nlQuery: "",
};

interface MetricCardData {
  title: string;
  value: string;
  trend: string;
  trendUp: boolean;
}

function buildFilterParams(f: FilterState): string {
  const p = new URLSearchParams();
  if (f.agent) p.set("agent", f.agent);
  if (f.issue) p.set("issue", f.issue);
  if (f.sentiment) p.set("sentiment", f.sentiment);
  if (f.dateFrom) p.set("date_from", f.dateFrom);
  if (f.dateTo) p.set("date_to", f.dateTo);
  return p.toString();
}

const Dashboard = () => {
  const [filters, setFilters] = useState<FilterState>(emptyFilters);
  const [refreshKey, setRefreshKey] = useState(0);
  const [metrics, setMetrics] = useState<MetricCardData[]>([]);
  const [isEmpty, setIsEmpty] = useState(false);
  const navigate = useNavigate();

  const filterParams = useMemo(() => buildFilterParams(filters), [filters]);

  // Unique key that changes with filters OR demo-data generation to force child re-fetches
  const dataKey = `${filterParams}__${refreshKey}`;

  useEffect(() => {
    apiFetch<{ cards: MetricCardData[]; empty: boolean }>(
      `/dashboard/metrics${filterParams ? "?" + filterParams : ""}`
    )
      .then((data) => {
        setMetrics(data.cards);
        setIsEmpty(data.empty);
      })
      .catch(console.error);
  }, [filterParams, refreshKey]);

  const handleGenerated = useCallback(() => setRefreshKey((k) => k + 1), []);

  // Append refreshKey to filterParams so children refetch on demo data generation
  const childFilterParams = filterParams
    ? `${filterParams}&_r=${refreshKey}`
    : refreshKey
      ? `_r=${refreshKey}`
      : "";

  return (
    <DashboardLayout>
      <div className="mb-6">
        <h1 className="text-[28px] font-semibold text-foreground tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">Overview of call quality and agent performance</p>
      </div>

      {/* Advanced Filters */}
      <DashboardFilters filters={filters} onChange={setFilters} />

      {/* Empty State — shown when DB has no calls */}
      {isEmpty && (
        <div className="mb-6 p-10 rounded-2xl border-2 border-dashed border-border bg-muted/20 flex flex-col items-center text-center gap-4">
          <div className="h-14 w-14 rounded-2xl bg-primary/10 flex items-center justify-center">
            <Upload className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">No call data yet</h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              Upload your first batch of call transcripts (CSV or JSON) to see real metrics, charts, agent performance, and AI insights here.
            </p>
          </div>
          <button
            onClick={() => navigate("/upload")}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-all"
          >
            Upload Calls <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
        {metrics.map((m, i) => (
          <MetricCard key={m.title} {...m} icon={icons[i]} index={i} />
        ))}
      </div>

      {/* Live Monitor + Risk Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <LiveCallMonitor />
        <RiskAlerts filterParams={childFilterParams} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <TopIssuesChart filterParams={childFilterParams} />
        <SentimentChart filterParams={childFilterParams} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <QualityTrendChart filterParams={childFilterParams} />
        <AgentScoreDistChart filterParams={childFilterParams} />
      </div>

      {/* Issue Heatmap */}
      <div className="mb-6">
        <IssueHeatmap filterParams={childFilterParams} />
      </div>

      {/* AI Insights + Leaderboard */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        <AIInsightsPanel filterParams={childFilterParams} />
        <AgentLeaderboard filterParams={childFilterParams} />
      </div>

      {/* Recent Summaries */}
      <div className="mb-6">
        <RecentSummaries filterParams={childFilterParams} />
      </div>

      {/* Agent Table */}
      <AgentTable filterParams={childFilterParams} />

      {/* Export + Demo */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-6">
        <ExportReports filterParams={childFilterParams} />
        <DemoDataGenerator onGenerated={handleGenerated} />
      </div>
    </DashboardLayout>
  );
};

export default Dashboard;
