import { useEffect, useRef, useState } from "react";
import { Send, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "./ChatMessage";
import { apiFetch } from "@/lib/api";

interface Message {
  id: number;
  role: "user" | "bot";
  content: string;
}

interface ChatWindowProps {
  onClose: () => void;
}

export function ChatWindow({ onClose }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([
    { id: 0, role: "bot", content: "Hi! I'm KenexAI assistant. Ask me about support data, call analytics, or anything else." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const nextId = useRef(1);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { id: nextId.current++, role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await apiFetch<{ answer: string; mode: string; sources: Array<Record<string, unknown>> }>("/chatbot/chat", {
        method: "POST",
        body: JSON.stringify({ question: text }),
      });
      const sourceBadge = res.mode === "RAG" && res.sources?.length
        ? `\n\n📊 _Sourced from ${res.sources.length} database record(s)_`
        : "";
      setMessages((prev) => [
        ...prev,
        { id: nextId.current++, role: "bot", content: res.answer + sourceBadge },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: nextId.current++, role: "bot", content: "Sorry, something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="fixed bottom-24 right-6 z-50 w-[380px] max-w-[calc(100vw-2rem)] h-[520px] max-h-[calc(100vh-8rem)] rounded-2xl border border-border bg-card shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-primary text-primary-foreground rounded-t-2xl">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="font-semibold text-sm">KenexAI Assistant</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-primary-foreground hover:bg-white/20"
          onClick={onClose}
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} role={msg.role} content={msg.content} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Thinking…</span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border px-3 py-2.5 bg-card">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a message…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            className="flex-1 bg-muted rounded-xl px-3.5 py-2.5 text-sm outline-none border-none placeholder:text-muted-foreground focus:ring-2 focus:ring-primary/30 disabled:opacity-50"
          />
          <Button
            size="icon"
            className="h-9 w-9 rounded-xl"
            onClick={sendMessage}
            disabled={loading || !input.trim()}
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
