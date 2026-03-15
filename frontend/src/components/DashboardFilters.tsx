import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Filter, X, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";

export interface FilterState {
  agent: string;
  issue: string;
  sentiment: string;
  duration: string;
  dateFrom: string;
  dateTo: string;
  nlQuery: string;
}

const DEFAULT_FILTERS: FilterState = {
  agent: "",
  issue: "",
  sentiment: "",
  duration: "",
  dateFrom: "",
  dateTo: "",
  nlQuery: "",
};

const sentimentOptions = ["", "Positive", "Neutral", "Negative"];
const durationOptions = ["", "< 2 min", "2-5 min", "5-10 min", "> 10 min"];

interface Props {
  filters: FilterState;
  onChange: (f: FilterState) => void;
}

export function DashboardFilters({ filters, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [agentOptions, setAgentOptions] = useState<{ id: string; name: string }[]>([]);
  const [issueOptions, setIssueOptions] = useState<string[]>([]);

  // Fetch dynamic filter options from DB
  useEffect(() => {
    apiFetch<{ agents: { id: string; name: string }[]; issues: string[] }>("/filters/options")
      .then((d) => {
        setAgentOptions(d.agents);
        setIssueOptions(d.issues);
      })
      .catch(console.error);
  }, []);

  const activeCount = [
    !!filters.agent,
    !!filters.issue,
    !!filters.sentiment,
    !!filters.duration,
    !!filters.dateFrom,
    !!filters.dateTo,
  ].filter(Boolean).length;

  const reset = () => onChange({ ...DEFAULT_FILTERS });

  return (
    <div className="mb-5">
      {/* AI Natural Language Search */}
      <div className="relative mb-3">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder='AI Search — e.g. "Show calls where customers complained about billing"'
          value={filters.nlQuery}
          onChange={(e) => onChange({ ...filters, nlQuery: e.target.value })}
          className="w-full h-10 pl-9 pr-4 rounded-lg bg-card ring-1 ring-border text-sm text-foreground placeholder:text-muted-foreground focus:ring-primary focus:outline-none transition-all"
        />
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg text-xs font-medium bg-card ring-1 ring-border hover:ring-primary/40 transition-all"
        >
          <Filter className="h-3.5 w-3.5" />
          Filters
          {activeCount > 0 && (
            <span className="ml-1 h-4 w-4 rounded-full bg-primary text-primary-foreground text-[10px] flex items-center justify-center">
              {activeCount}
            </span>
          )}
        </button>
        {activeCount > 0 && (
          <button onClick={reset} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-3 w-3" /> Clear all
          </button>
        )}
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-3"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div>
              <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Agent</label>
              <select
                value={filters.agent}
                onChange={(e) => onChange({ ...filters, agent: e.target.value })}
                className="w-full h-8 px-2 rounded-md bg-card ring-1 ring-border text-xs text-foreground focus:ring-primary focus:outline-none appearance-none cursor-pointer"
              >
                <option value="">All Agents</option>
                {agentOptions.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.id})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Issue</label>
              <select
                value={filters.issue}
                onChange={(e) => onChange({ ...filters, issue: e.target.value })}
                className="w-full h-8 px-2 rounded-md bg-card ring-1 ring-border text-xs text-foreground focus:ring-primary focus:outline-none appearance-none cursor-pointer"
              >
                <option value="">All Issues</option>
                {issueOptions.map((i) => (
                  <option key={i} value={i}>{i}</option>
                ))}
              </select>
            </div>
            <SelectFilter label="Sentiment" value={filters.sentiment} options={sentimentOptions} onChange={(v) => onChange({ ...filters, sentiment: v })} />
            <SelectFilter label="Duration" value={filters.duration} options={durationOptions} onChange={(v) => onChange({ ...filters, duration: v })} />
            <div>
              <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">From</label>
              <input
                type="date"
                value={filters.dateFrom}
                onChange={(e) => onChange({ ...filters, dateFrom: e.target.value })}
                className="w-full h-8 px-2 rounded-md bg-card ring-1 ring-border text-xs text-foreground focus:ring-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">To</label>
              <input
                type="date"
                value={filters.dateTo}
                onChange={(e) => onChange({ ...filters, dateTo: e.target.value })}
                className="w-full h-8 px-2 rounded-md bg-card ring-1 ring-border text-xs text-foreground focus:ring-primary focus:outline-none"
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SelectFilter({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full h-8 px-2 rounded-md bg-card ring-1 ring-border text-xs text-foreground focus:ring-primary focus:outline-none appearance-none cursor-pointer"
      >
        <option value="">All {label}s</option>
        {options.filter(Boolean).map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}
