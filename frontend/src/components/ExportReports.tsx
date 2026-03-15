import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Download, FileSpreadsheet, FileText, File, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface ReportRow {
  callId: string;
  agent: string;
  score: number;
  sentiment: string;
  issue: string;
  resolved: boolean;
  duration: number;
  date: string;
}

interface Props {
  filterParams?: string;
}

export function ExportReports({ filterParams = "" }: Props) {
  const [exporting, setExporting] = useState<string | null>(null);
  const [data, setData] = useState<ReportRow[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await apiFetch<{ data: ReportRow[] }>(`/export-data${filterParams ? "?" + filterParams : ""}`);
      setData(res.data);
      return res.data;
    } catch {
      return data;
    } finally {
      setLoading(false);
    }
  };

  // Pre-fetch so we know the count
  useEffect(() => {
    fetchData();
  }, [filterParams]);

  const exportCSV = async () => {
    setExporting("csv");
    const rows = await fetchData();
    const headers = "Call ID,Agent,Score,Sentiment,Issue,Resolved,Duration,Date\n";
    const csv = rows.map((r) => `${r.callId},${r.agent},${r.score},${r.sentiment},${r.issue},${r.resolved},${r.duration},${r.date}`).join("\n");
    const blob = new Blob([headers + csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "call_analytics_report.csv";
    a.click();
    URL.revokeObjectURL(url);
    setTimeout(() => setExporting(null), 1000);
  };

  const exportExcel = async () => {
    setExporting("excel");
    const rows = await fetchData();
    const XLSX = await import("xlsx");
    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Report");
    XLSX.writeFile(wb, "call_analytics_report.xlsx");
    setTimeout(() => setExporting(null), 1000);
  };

  const exportPDF = async () => {
    setExporting("pdf");
    const rows = await fetchData();
    const { jsPDF } = await import("jspdf");
    const autoTable = (await import("jspdf-autotable")).default;
    const doc = new jsPDF();
    doc.setFontSize(16);
    doc.text("ReviewSense AI — Call Analytics Report", 14, 20);
    doc.setFontSize(10);
    doc.text(`Generated: ${new Date().toLocaleDateString()} | ${rows.length} calls`, 14, 28);
    autoTable(doc, {
      startY: 35,
      head: [["Call ID", "Agent", "Score", "Sentiment", "Issue", "Resolved"]],
      body: rows.map((r) => [r.callId, r.agent, r.score, r.sentiment, r.issue, r.resolved ? "Yes" : "No"]),
    });
    doc.save("call_analytics_report.pdf");
    setTimeout(() => setExporting(null), 1000);
  };

  return (
    <motion.div
      className="chart-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.65 }}
    >
      <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-4">
        <Download className="h-3.5 w-3.5" />
        Export Reports
        {data.length > 0 && <span className="text-[10px] text-muted-foreground/70">({data.length} calls)</span>}
      </h3>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={exportCSV}
          disabled={!!exporting || loading || data.length === 0}
          className="inline-flex items-center gap-2 h-9 px-4 rounded-lg text-sm font-medium bg-muted/50 ring-1 ring-border hover:ring-primary/40 hover:bg-primary/5 transition-all disabled:opacity-50"
        >
          <FileText className="h-4 w-4" />
          {exporting === "csv" ? <><Loader2 className="h-4 w-4 animate-spin" /> Exporting...</> : "CSV"}
        </button>
        <button
          onClick={exportExcel}
          disabled={!!exporting || loading || data.length === 0}
          className="inline-flex items-center gap-2 h-9 px-4 rounded-lg text-sm font-medium bg-muted/50 ring-1 ring-border hover:ring-success/40 hover:bg-success/5 transition-all disabled:opacity-50"
        >
          <FileSpreadsheet className="h-4 w-4" />
          {exporting === "excel" ? <><Loader2 className="h-4 w-4 animate-spin" /> Exporting...</> : "Excel"}
        </button>
        <button
          onClick={exportPDF}
          disabled={!!exporting || loading || data.length === 0}
          className="inline-flex items-center gap-2 h-9 px-4 rounded-lg text-sm font-medium bg-muted/50 ring-1 ring-border hover:ring-danger/40 hover:bg-danger/5 transition-all disabled:opacity-50"
        >
          <File className="h-4 w-4" />
          {exporting === "pdf" ? <><Loader2 className="h-4 w-4 animate-spin" /> Exporting...</> : "PDF"}
        </button>
      </div>
    </motion.div>
  );
}
