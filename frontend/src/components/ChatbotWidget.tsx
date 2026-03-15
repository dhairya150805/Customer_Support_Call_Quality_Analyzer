import { useState } from "react";
import { MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatWindow } from "./ChatWindow";
import { isAuthenticated } from "@/lib/api";

export function ChatbotWidget() {
  const [open, setOpen] = useState(false);

  // Only show the chatbot for authenticated users
  if (!isAuthenticated()) return null;

  return (
    <>
      {open && <ChatWindow onClose={() => setOpen(false)} />}

      <Button
        onClick={() => setOpen((prev) => !prev)}
        size="icon"
        className="fixed bottom-6 right-6 z-50 h-14 w-14 rounded-full shadow-lg hover:shadow-xl transition-shadow"
        aria-label={open ? "Close chatbot" : "Open chatbot"}
      >
        <MessageCircle className="w-6 h-6" />
      </Button>
    </>
  );
}
