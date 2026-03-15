import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { PrivateRoute } from "@/components/PrivateRoute";
import { ChatbotWidget } from "@/components/ChatbotWidget";

import Index from "./pages/Index.tsx";
import UploadCalls from "./pages/UploadCalls.tsx";
import CallInsights from "./pages/CallInsights.tsx";
import AgentPerformance from "./pages/AgentPerformance.tsx";
import EvaluationFramework from "./pages/EvaluationFramework.tsx";
import SettingsPage from "./pages/Settings.tsx";
import Register from "./pages/Register.tsx";
import Login from "./pages/Login.tsx";
import NotFound from "./pages/NotFound.tsx";
import LiveTranscriptAnalyzer from "./pages/LiveTranscriptAnalyzer.tsx";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          {/* ── Public routes ── */}
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* ── Protected routes ── */}
          <Route path="/"         element={<PrivateRoute><Index /></PrivateRoute>} />
          <Route path="/upload"   element={<PrivateRoute><UploadCalls /></PrivateRoute>} />
          <Route path="/insights" element={<PrivateRoute><CallInsights /></PrivateRoute>} />
          <Route path="/call-insights" element={<Navigate to="/insights" replace />} />
          <Route path="/agents"   element={<PrivateRoute><AgentPerformance /></PrivateRoute>} />
          <Route path="/framework"element={<PrivateRoute><EvaluationFramework /></PrivateRoute>} />
          <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
          <Route path="/live-analyzer" element={<PrivateRoute><LiveTranscriptAnalyzer /></PrivateRoute>} />

          {/* ── Fallback ── */}
          <Route path="*" element={<NotFound />} />
        </Routes>
        <ChatbotWidget />
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
