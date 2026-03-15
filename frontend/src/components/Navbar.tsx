import { Search, Bell, LogOut } from "lucide-react";
import { DarkModeToggle } from "./DarkModeToggle";
import { useNavigate } from "react-router-dom";
import { clearToken } from "@/lib/api";

export function Navbar() {
  const navigate = useNavigate();
  const company  = (() => {
    try { return JSON.parse(localStorage.getItem("rs_company") || "{}"); }
    catch { return {}; }
  })();
  const initials = (company.name || "CX").slice(0, 2).toUpperCase();

  const handleLogout = () => {
    clearToken();
    navigate("/login");
  };

  return (
    <header className="h-16 bg-card border-b border-border flex items-center justify-between px-6 sticky top-0 z-20">
      {/* Search */}
      <div className="relative w-full max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search call ID, agent ID, issue..."
          className="w-full h-9 pl-9 pr-4 rounded-lg bg-muted/60 text-sm text-foreground placeholder:text-muted-foreground ring-1 ring-border focus:ring-primary focus:outline-none transition-all"
        />
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2 ml-6">
        <DarkModeToggle />
        <button className="relative p-2 rounded-lg hover:bg-muted transition-colors">
          <Bell className="h-[18px] w-[18px] text-muted-foreground" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 bg-danger rounded-full" />
        </button>

        <div className="flex items-center gap-3 ml-2">
          <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-semibold">
            {initials}
          </div>
          <div className="hidden sm:block">
            <p className="text-sm font-medium text-foreground leading-none">{company.name || "Company"}</p>
            <p className="text-xs text-muted-foreground">{company.email || ""}</p>
          </div>
        </div>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="ml-1 p-2 rounded-lg hover:bg-danger/10 hover:text-danger text-muted-foreground transition-colors"
          title="Sign out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}

