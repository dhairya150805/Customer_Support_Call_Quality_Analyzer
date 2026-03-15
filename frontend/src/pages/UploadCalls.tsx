import { useState, useRef } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Upload, FileText, Loader2, CheckCircle2, AlertCircle, X, FileJson } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { BASE_URL, getToken } from "@/lib/api";

type FileStatus = "waiting" | "uploading" | "done" | "error";

type FileItem = {
  file: File;
  status: FileStatus;
  result?: { 
    total: number; 
    calls: { contactId: string; sentiment?: string; quality_score?: number; status: string; message?: string }[];
    notifications?: string[];
  };
  error?: string;
};

type TranscriptResult = { quality_score: number; sentiment: string; insights: { summary: string } };

const UploadCalls = () => {
  const [files, setFiles]     = useState<FileItem[]>([]);
  const [running, setRunning] = useState(false);
  const [transcript, setTranscript]               = useState("");
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [transcriptResult, setTranscriptResult]   = useState<TranscriptResult | null>(null);
  const [transcriptError, setTranscriptError]     = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── File selection ─────────────────────────────────────────────────────────
  const onFilesSelected = (selected: FileList | null) => {
    if (!selected) return;
    const newItems: FileItem[] = Array.from(selected).map((f) => ({ file: f, status: "waiting" }));
    setFiles((prev) => [...prev, ...newItems]);
  };

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  // ── Upload all files ───────────────────────────────────────────────────────
  const uploadAll = async () => {
    if (files.length === 0 || running) return;
    setRunning(true);

    for (let i = 0; i < files.length; i++) {
      if (files[i].status === "done") continue;

      // set uploading
      setFiles((prev) => prev.map((f, idx) => idx === i ? { ...f, status: "uploading" } : f));

      try {
        const formData = new FormData();
        formData.append("file", files[i].file);
        const res = await fetch(`${BASE_URL}/upload-calls`, {
          method: "POST",
          headers: { Authorization: `Bearer ${getToken()}` },
          body: formData,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload failed");

        setFiles((prev) => prev.map((f, idx) =>
          idx === i ? { ...f, status: "done", result: data } : f
        ));
      } catch (e: any) {
        setFiles((prev) => prev.map((f, idx) =>
          idx === i ? { ...f, status: "error", error: e.message } : f
        ));
      }
    }
    setRunning(false);
  };

  // ── Analyze transcript ─────────────────────────────────────────────────────
  const analyzeTranscript = async () => {
    if (!transcript.trim()) { setTranscriptError("Please paste a transcript first."); return; }
    setTranscriptError(null);
    setTranscriptResult(null);
    setTranscriptLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/analyze-transcript`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ text: transcript }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Analysis failed");
      setTranscriptResult(data);
    } catch (e: any) {
      setTranscriptError(e.message);
    } finally {
      setTranscriptLoading(false);
    }
  };

  const totalDone     = files.filter((f) => f.status === "done").length;
  const totalRows     = files.filter((f) => f.status === "done").reduce((s, f) => s + (f.result?.total || 0), 0);
  const hasWaiting    = files.some((f) => f.status === "waiting");

  return (
    <DashboardLayout>
      <div className="mb-6">
        <h1 className="text-[28px] font-semibold text-foreground tracking-tight">Upload Calls</h1>
        <p className="text-sm text-muted-foreground mt-1">Upload one or more CSV / JSON files for AI analysis</p>
      </div>

      <div className="w-full max-w-2xl space-y-5">
        {/* ── Drop Zone ── */}
        <motion.div
          className="chart-card"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.2, 0, 0, 1] }}
        >
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-4">
            Upload CSV / JSON Files
          </h3>

          {/* Drop area */}
          <label
            className="flex flex-col items-center justify-center h-36 border-2 border-dashed border-border rounded-xl cursor-pointer hover:border-primary/40 hover:bg-primary/5 transition-all"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); onFilesSelected(e.dataTransfer.files); }}
          >
            <Upload className="h-7 w-7 text-muted-foreground mb-2" />
            <span className="text-sm font-medium text-foreground">Drag & drop or click to choose files</span>
            <span className="text-xs text-muted-foreground mt-1">CSV, JSON — multiple files allowed</span>
            <input
              ref={inputRef}
              type="file"
              className="hidden"
              accept=".csv,.json"
              multiple
              onChange={(e) => onFilesSelected(e.target.files)}
            />
          </label>

          {/* File list */}
          <AnimatePresence>
            {files.length > 0 && (
              <motion.div
                className="mt-4 space-y-2"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              >
                {files.map((item, idx) => (
                  <motion.div
                    key={`${item.file.name}-${idx}`}
                    className="flex items-center gap-3 p-3 rounded-lg bg-muted/40 ring-1 ring-border"
                    initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                  >
                    <FileJson className="h-4 w-4 text-primary shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">{item.file.name}</p>
                      <p className="text-xs text-muted-foreground">{(item.file.size / 1024).toFixed(1)} KB</p>
                    </div>

                    {/* Status badge */}
                    {item.status === "waiting" && (
                      <span className="text-xs text-muted-foreground px-2 py-0.5 bg-muted rounded-full">Waiting</span>
                    )}
                    {item.status === "uploading" && (
                      <span className="flex items-center gap-1 text-xs text-primary px-2 py-0.5 bg-primary/10 rounded-full">
                        <Loader2 className="h-3 w-3 animate-spin" /> Analyzing...
                      </span>
                    )}
                    {item.status === "done" && (
                      <span className="flex items-center gap-1 text-xs text-success px-2 py-0.5 bg-success/10 rounded-full">
                        <CheckCircle2 className="h-3 w-3" /> {item.result?.total} rows
                      </span>
                    )}
                    {item.status === "error" && (
                      <span className="text-xs text-danger px-2 py-0.5 bg-danger/10 rounded-full truncate max-w-[140px]" title={item.error}>
                        ✕ {item.error}
                      </span>
                    )}

                    {/* Remove */}
                    {item.status !== "uploading" && (
                      <button onClick={() => removeFile(idx)} className="text-muted-foreground hover:text-danger transition-colors shrink-0">
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </motion.div>
                ))}

                {/* Upload button */}
                {hasWaiting && (
                  <button
                    onClick={uploadAll}
                    disabled={running}
                    className="w-full h-10 mt-2 bg-primary text-primary-foreground rounded-lg text-sm font-semibold hover:opacity-90 transition-all disabled:opacity-60"
                  >
                    {running ? (
                      <span className="flex items-center justify-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" /> Analyzing {files.filter(f=>f.status==="uploading").length > 0 ? `file ${files.findIndex(f=>f.status==="uploading")+1} of ${files.length}` : "..."}
                      </span>
                    ) : (
                      `Analyze ${files.filter(f=>f.status==="waiting").length} File${files.filter(f=>f.status==="waiting").length > 1 ? "s" : ""}`
                    )}
                  </button>
                )}

                {/* Summary after all done */}
                {totalDone > 0 && !hasWaiting && !running && (
                  <motion.div
                    className="flex items-center gap-2 p-3 rounded-lg bg-success/10 ring-1 ring-success/20 text-sm text-success"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    All done — {totalDone} file{totalDone > 1 ? "s" : ""} processed, {totalRows} calls analyzed and saved to database.
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* ── Per-file Results ── */}
        <AnimatePresence>
          {files.filter((f) => f.status === "done" && f.result && f.result.calls.length > 0).map((item, i) => (
            <motion.div
              key={`result-${i}`}
              className="chart-card"
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
            >
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                {item.file.name} — {item.result!.total} calls
              </p>
              <div className="space-y-2">
                {item.result!.calls.slice(0, 5).map((c) => (
                  <div key={c.contactId} className="flex items-center justify-between p-2.5 rounded-lg bg-muted/30 text-sm">
                    <span className="font-medium text-foreground">{c.contactId}</span>
                    {c.status === "skipped" ? (
                      <span className="text-xs text-warning flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" /> {c.message}
                      </span>
                    ) : (
                      <>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          c.sentiment === "Positive" ? "bg-success/10 text-success" :
                          c.sentiment === "Negative" ? "bg-danger/10 text-danger" : "bg-warning/10 text-warning"
                        }`}>{c.sentiment}</span>
                        <span className="text-xs text-muted-foreground">Score: {c.quality_score}</span>
                      </>
                    )}
                  </div>
                ))}
                {item.result!.total > 5 && (
                  <p className="text-xs text-muted-foreground text-center pt-1">
                    + {item.result!.total - 5} more rows processed
                  </p>
                )}
              </div>

              {/* ── Risk Notifications ── */}
              {item.result!.notifications && item.result!.notifications.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-xs font-medium text-danger uppercase tracking-wider mb-2">Risk Alerts</p>
                  {item.result!.notifications.map((note, idx) => (
                    <motion.div 
                      key={idx}
                      initial={{ opacity: 0, x: -5 }} animate={{ opacity: 1, x: 0 }}
                      className="flex items-start gap-2 p-3 rounded-lg bg-danger/10 ring-1 ring-danger/20 text-sm text-danger"
                    >
                      <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                      <span>{note}</span>
                    </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {/* ── Paste Transcript ── */}
        <motion.div
          className="chart-card"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1, ease: [0.2, 0, 0, 1] }}
        >
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-4">
            <FileText className="inline h-3.5 w-3.5 mr-1.5 -mt-0.5" />
            Or Paste a Single Transcript
          </h3>
          <textarea
            className="w-full h-36 p-4 rounded-lg bg-muted/40 ring-1 ring-border text-sm text-foreground placeholder:text-muted-foreground focus:ring-primary focus:outline-none resize-none transition-all"
            placeholder={"Agent: Hello, how can I help?\nCustomer: My internet is down..."}
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
          />
          <button
            onClick={analyzeTranscript}
            disabled={transcriptLoading}
            className="mt-3 h-10 px-6 bg-primary text-primary-foreground rounded-lg font-medium text-sm hover:opacity-90 transition-all disabled:opacity-60"
          >
            {transcriptLoading ? (
              <span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Analyzing...</span>
            ) : "Analyze Transcript"}
          </button>

          {/* Transcript error */}
          {transcriptError && (
            <motion.div
              className="mt-3 flex items-center gap-2 p-3 rounded-lg bg-danger/10 ring-1 ring-danger/20 text-sm text-danger"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            >
              <AlertCircle className="h-4 w-4 shrink-0" /> {transcriptError}
            </motion.div>
          )}

          {/* Transcript result */}
          {transcriptResult && !transcriptLoading && (
            <motion.div className="mt-4 grid grid-cols-2 gap-3" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div className="p-3 rounded-lg bg-muted/30">
                <p className="text-xs text-muted-foreground mb-0.5">Quality Score</p>
                <p className="text-xl font-bold text-foreground">{transcriptResult.quality_score}<span className="text-xs text-muted-foreground">/100</span></p>
              </div>
              <div className="p-3 rounded-lg bg-muted/30">
                <p className="text-xs text-muted-foreground mb-0.5">Sentiment</p>
                <p className={`text-sm font-semibold ${
                  transcriptResult.sentiment === "Positive" ? "text-success" :
                  transcriptResult.sentiment === "Negative" ? "text-danger" : "text-warning"
                }`}>{transcriptResult.sentiment}</p>
              </div>
              <div className="col-span-2 p-3 rounded-lg bg-muted/30">
                <p className="text-xs text-muted-foreground mb-1">Summary</p>
                <p className="text-xs text-foreground leading-relaxed">{transcriptResult.insights?.summary}</p>
              </div>
              <p className="col-span-2 text-xs text-primary">
                → Check <a href="/insights" className="underline">Call Insights</a> for full analysis
              </p>
            </motion.div>
          )}
        </motion.div>
      </div>
    </DashboardLayout>
  );
};

export default UploadCalls;
