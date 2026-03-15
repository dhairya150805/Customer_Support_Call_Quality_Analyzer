import { useState } from "react";
import { motion } from "framer-motion";
import { Wand2, Loader2, CheckCircle2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Props {
  onGenerated?: () => void;
}

export function DemoDataGenerator({ onGenerated }: Props) {
  const [status, setStatus] = useState<"idle" | "generating" | "done" | "error">("idle");
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");

  const generate = async () => {
    setStatus("generating");
    setCount(0);
    setError("");

    // Show progress animation
    let current = 0;
    const interval = setInterval(() => {
      current += Math.floor(Math.random() * 5) + 1;
      if (current > 45) current = 45;
      setCount(current);
    }, 200);

    try {
      const res = await apiFetch<{ created: number; message: string }>("/generate-demo", { method: "POST" });
      clearInterval(interval);
      setCount(res.created);
      setStatus("done");
      // Trigger parent refresh
      onGenerated?.();
    } catch (err: unknown) {
      clearInterval(interval);
      setError(err instanceof Error ? err.message : "Failed to generate");
      setStatus("error");
    }
  };

  return (
    <motion.div
      className="chart-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.7 }}
    >
      <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-3">
        <Wand2 className="h-3.5 w-3.5" />
        Demo Data Generator
      </h3>
      <p className="text-xs text-muted-foreground mb-3">Generate 50 sample calls in the database and refresh all dashboard data.</p>
      <div className="flex items-center gap-3">
        <button
          onClick={generate}
          disabled={status === "generating"}
          className="inline-flex items-center gap-2 h-9 px-4 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 active:scale-[0.97] transition-all disabled:opacity-60 shadow-sm"
        >
          {status === "generating" ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating... {count}/50
            </>
          ) : status === "done" ? (
            <>
              <CheckCircle2 className="h-4 w-4" />
              {count} calls generated!
            </>
          ) : status === "error" ? (
            <>
              <Wand2 className="h-4 w-4" />
              Try Again
            </>
          ) : (
            <>
              <Wand2 className="h-4 w-4" />
              Generate 50 Sample Calls
            </>
          )}
        </button>
        {(status === "done" || status === "error") && (
          <button
            onClick={() => setStatus("idle")}
            className="text-xs text-primary hover:underline"
          >
            Reset
          </button>
        )}
      </div>
      {error && <p className="text-xs text-danger mt-2">{error}</p>}
      {status === "generating" && (
        <div className="mt-3 h-1.5 bg-muted rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-primary rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${(count / 50) * 100}%` }}
            transition={{ duration: 0.2 }}
          />
        </div>
      )}
    </motion.div>
  );
}
