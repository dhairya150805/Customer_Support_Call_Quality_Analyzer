import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { BrainCircuit, Mail, Lock, Loader2, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { setToken, BASE_URL } from "@/lib/api";

const Login = () => {
  const navigate = useNavigate();
  const [form, setForm]       = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.email.trim() || !form.password.trim()) {
      setError("Email and password are required.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed.");
      setToken(data.access_token);
      localStorage.setItem("rs_company", JSON.stringify(data.company));
      navigate("/");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <motion.div
        className="w-full max-w-md"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.2, 0, 0, 1] }}
      >
        {/* Logo */}
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <div className="h-10 w-10 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/25">
            <BrainCircuit className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="text-xl font-semibold text-foreground">ReviewSense AI</span>
        </div>

        {/* Card */}
        <div className="chart-card">
          <h1 className="text-2xl font-bold text-foreground mb-1">Welcome back</h1>
          <p className="text-sm text-muted-foreground mb-6">Sign in to your company dashboard</p>

          {error && (
            <motion.div
              className="flex items-center gap-2 p-3 rounded-lg bg-danger/10 ring-1 ring-danger/20 text-sm text-danger mb-4"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            >
              <AlertCircle className="h-4 w-4 shrink-0" /> {error}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="email"
                  placeholder="support@company.com"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full h-10 pl-10 pr-4 rounded-lg bg-muted/40 ring-1 ring-border text-sm text-foreground placeholder:text-muted-foreground/60 focus:ring-primary focus:outline-none transition-all"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="password"
                  placeholder="Your password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="w-full h-10 pl-10 pr-4 rounded-lg bg-muted/40 ring-1 ring-border text-sm text-foreground placeholder:text-muted-foreground/60 focus:ring-primary focus:outline-none transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full h-10 bg-primary text-primary-foreground rounded-lg text-sm font-semibold hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-60 shadow-md shadow-primary/20 mt-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" /> Signing in…
                </span>
              ) : "Sign In"}
            </button>
          </form>

          <p className="text-xs text-muted-foreground text-center mt-5">
            Don't have an account?{" "}
            <Link to="/register" className="text-primary font-medium hover:underline">
              Register your company
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
