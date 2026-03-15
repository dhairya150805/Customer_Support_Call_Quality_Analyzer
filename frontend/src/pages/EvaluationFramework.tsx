import { useState, useEffect, useRef } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus, GripVertical, Save, Loader2, CheckCircle2,
  Trash2, Pencil, Check, X, ChevronDown, ChevronUp,
} from "lucide-react";
import { apiFetch, BASE_URL } from "@/lib/api";

/* ── Types ─────────────────────────────────────────────────────────────────── */
interface Criteria {
  id: string;
  label: string;
  weight: number;
  enabled: boolean;
}

interface Section {
  id: string;
  name: string;
  weight: number;
  criteria: Criteria[];
  collapsed?: boolean;
}

/* ── Inline-edit input ─────────────────────────────────────────────────────── */
function InlineEdit({
  value, onSave, className = "",
}: {
  value: string;
  onSave: (v: string) => void;
  className?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed) onSave(trimmed);
    else setDraft(value);
    setEditing(false);
  };

  if (!editing) {
    return (
      <span
        className={`cursor-pointer group/edit inline-flex items-center gap-1.5 ${className}`}
        onClick={() => { setDraft(value); setEditing(true); }}
      >
        <span>{value}</span>
        <Pencil className="h-3 w-3 text-muted-foreground/0 group-hover/edit:text-muted-foreground transition-colors" />
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1">
      <input
        ref={ref}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setEditing(false); }}
        onBlur={commit}
        className={`bg-muted/60 border border-border rounded px-2 py-0.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary ${className}`}
      />
    </span>
  );
}

/* ── Toggle switch ─────────────────────────────────────────────────────────── */
function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ${
        checked ? "bg-primary" : "bg-muted-foreground/30"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition-transform duration-200 mt-0.5 ${
          checked ? "translate-x-[18px]" : "translate-x-[2px]"
        }`}
      />
    </button>
  );
}

/* ── Main component ────────────────────────────────────────────────────────── */
const EvaluationFramework = () => {
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    apiFetch<{ sections: Section[] }>("/evaluation-framework")
      .then((d) => {
        // Ensure every criteria has `enabled` (backward compat)
        const patched = d.sections.map((s) => ({
          ...s,
          collapsed: false,
          criteria: s.criteria.map((c) => ({ ...c, enabled: c.enabled !== false })),
        }));
        setSections(patched);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  /* ── Helpers to update state ─────────────────────────────────────────────── */
  const update = (fn: (prev: Section[]) => Section[]) => {
    setSections((prev) => fn(prev));
    setDirty(true);
  };

  const updateCriteria = (sectionId: string, criteriaId: string, patch: Partial<Criteria>) => {
    update((prev) =>
      prev.map((s) =>
        s.id === sectionId
          ? { ...s, criteria: s.criteria.map((c) => (c.id === criteriaId ? { ...c, ...patch } : c)) }
          : s
      )
    );
  };

  const deleteCriteria = (sectionId: string, criteriaId: string) => {
    update((prev) =>
      prev.map((s) =>
        s.id === sectionId ? { ...s, criteria: s.criteria.filter((c) => c.id !== criteriaId) } : s
      )
    );
  };

  const addCriteria = (sectionId: string) => {
    const newId = `c_${Date.now()}`;
    update((prev) =>
      prev.map((s) =>
        s.id === sectionId
          ? { ...s, criteria: [...s.criteria, { id: newId, label: "New Criteria", weight: 5, enabled: true }] }
          : s
      )
    );
  };

  const updateSection = (sectionId: string, patch: Partial<Section>) => {
    update((prev) => prev.map((s) => (s.id === sectionId ? { ...s, ...patch } : s)));
  };

  const deleteSection = (sectionId: string) => {
    update((prev) => prev.filter((s) => s.id !== sectionId));
  };

  const addSection = () => {
    const newId = `s_${Date.now()}`;
    update((prev) => [
      ...prev,
      { id: newId, name: "New Section", weight: 10, criteria: [], collapsed: false },
    ]);
  };

  const toggleCollapse = (sectionId: string) => {
    setSections((prev) =>
      prev.map((s) => (s.id === sectionId ? { ...s, collapsed: !s.collapsed } : s))
    );
  };

  /* ── Computed: total weight, section active weight ───────────────────────── */
  const totalWeight = sections.reduce((sum, s) => sum + s.weight, 0);
  const enabledWeight = (s: Section) =>
    s.criteria.filter((c) => c.enabled).reduce((sum, c) => sum + c.weight, 0);

  /* ── Save ────────────────────────────────────────────────────────────────── */
  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const token = localStorage.getItem("token");
      await fetch(`${BASE_URL}/evaluation-framework`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(sections),
      });
      setSaved(true);
      setDirty(false);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout>
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-[28px] font-semibold text-foreground tracking-tight">Evaluation Framework</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configure scoring rules and criteria weights
            {totalWeight !== 100 && (
              <span className="ml-2 text-warning font-medium">
                (Total: {totalWeight}% — should be 100%)
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={saving || loading || !dirty}
            className={`flex items-center gap-2 h-9 px-4 rounded-lg text-sm font-medium transition-all active:scale-[0.97] disabled:opacity-60 ${
              saved
                ? "bg-green-600 text-white"
                : "bg-primary text-primary-foreground hover:opacity-90"
            }`}
          >
            {saving ? (
              <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…</>
            ) : saved ? (
              <><CheckCircle2 className="h-3.5 w-3.5" /> Saved!</>
            ) : (
              <><Save className="h-3.5 w-3.5" /> Save Framework</>
            )}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm py-12 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading framework…
        </div>
      ) : (
        <div className="max-w-3xl space-y-5">
          <AnimatePresence mode="popLayout">
            {sections.map((section, si) => (
              <motion.div
                key={section.id}
                className="chart-card"
                layout
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.3, delay: si * 0.03 }}
              >
                {/* ── Section header ───────────────────────────────────────── */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleCollapse(section.id)}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {section.collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
                    </button>
                    <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                      <InlineEdit
                        value={section.name}
                        onSave={(v) => updateSection(section.id, { name: v })}
                        className="text-sm font-semibold"
                      />
                    </h3>
                    <span className="text-xs text-muted-foreground">&mdash;</span>
                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={section.weight}
                        onChange={(e) => updateSection(section.id, { weight: Math.max(0, Math.min(100, Number(e.target.value))) })}
                        className="w-12 h-6 bg-muted/60 border border-border rounded px-1.5 text-xs font-medium text-foreground text-center focus:outline-none focus:ring-1 focus:ring-primary tabular-nums"
                      />
                      <span className="text-xs text-muted-foreground">%</span>
                    </div>
                    <span className="text-[10px] text-muted-foreground/70 tabular-nums">
                      ({enabledWeight(section)}/{section.weight} used)
                    </span>
                  </div>
                  <button
                    onClick={() => deleteSection(section.id)}
                    className="text-muted-foreground/40 hover:text-red-500 transition-colors p-1"
                    title="Delete section"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>

                {/* ── Criteria list ────────────────────────────────────────── */}
                {!section.collapsed && (
                  <div className="space-y-2">
                    <AnimatePresence mode="popLayout">
                      {section.criteria.map((c) => (
                        <motion.div
                          key={c.id}
                          layout
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 10, height: 0 }}
                          transition={{ duration: 0.2 }}
                          className={`flex items-center gap-3 group py-1.5 px-2 rounded-md transition-colors ${
                            c.enabled ? "hover:bg-muted/40" : "opacity-50"
                          }`}
                        >
                          <GripVertical className="h-4 w-4 text-muted-foreground/20 group-hover:text-muted-foreground/60 transition-colors cursor-grab shrink-0" />

                          {/* Toggle */}
                          <Toggle
                            checked={c.enabled}
                            onChange={(v) => updateCriteria(section.id, c.id, { enabled: v })}
                          />

                          {/* Label — inline editable */}
                          <div className="flex-1 min-w-0">
                            <InlineEdit
                              value={c.label}
                              onSave={(v) => updateCriteria(section.id, c.id, { label: v })}
                              className={`text-sm ${c.enabled ? "text-foreground" : "text-muted-foreground line-through"}`}
                            />
                          </div>

                          {/* Weight slider + value */}
                          <div className="flex items-center gap-2 w-36 shrink-0">
                            <input
                              type="range"
                              min={0}
                              max={section.weight}
                              value={c.weight}
                              disabled={!c.enabled}
                              onChange={(e) => updateCriteria(section.id, c.id, { weight: Number(e.target.value) })}
                              className="flex-1 accent-primary h-1.5 disabled:opacity-40"
                            />
                            <input
                              type="number"
                              min={0}
                              max={section.weight}
                              value={c.weight}
                              disabled={!c.enabled}
                              onChange={(e) =>
                                updateCriteria(section.id, c.id, {
                                  weight: Math.max(0, Math.min(section.weight, Number(e.target.value))),
                                })
                              }
                              className="w-10 h-6 bg-muted/60 border border-border rounded px-1 text-xs font-medium text-foreground text-center tabular-nums focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-40"
                            />
                          </div>

                          {/* Delete */}
                          <button
                            onClick={() => deleteCriteria(section.id, c.id)}
                            className="text-muted-foreground/0 group-hover:text-muted-foreground/60 hover:!text-red-500 transition-colors p-0.5 shrink-0"
                            title="Remove criteria"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </motion.div>
                      ))}
                    </AnimatePresence>

                    {/* Add criteria */}
                    <button
                      onClick={() => addCriteria(section.id)}
                      className="mt-2 flex items-center gap-1.5 text-xs text-primary font-medium hover:opacity-80 transition-opacity"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Add Criteria
                    </button>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {/* ── Add section ────────────────────────────────────────────────── */}
          <button
            onClick={addSection}
            className="w-full py-3 border-2 border-dashed border-border rounded-xl text-sm text-muted-foreground font-medium hover:border-primary hover:text-primary transition-colors flex items-center justify-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Add Section
          </button>
        </div>
      )}
    </DashboardLayout>
  );
};

export default EvaluationFramework;
