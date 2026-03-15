import { cn } from "@/lib/utils";
import { Bot, User } from "lucide-react";

interface ChatMessageProps {
  role: "user" | "bot";
  content: string;
}

export function ChatMessage({ role, content }: ChatMessageProps) {
  const isBot = role === "bot";

  return (
    <div className={cn("flex gap-2.5 max-w-full", isBot ? "justify-start" : "justify-end")}>
      {isBot && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center mt-0.5">
          <Bot className="w-4 h-4 text-primary" />
        </div>
      )}
      <div
        className={cn(
          "rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed max-w-[80%] whitespace-pre-wrap break-words",
          isBot
            ? "bg-muted text-foreground rounded-tl-md"
            : "bg-primary text-primary-foreground rounded-tr-md"
        )}
      >
        {content}
      </div>
      {!isBot && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary flex items-center justify-center mt-0.5">
          <User className="w-4 h-4 text-primary-foreground" />
        </div>
      )}
    </div>
  );
}
