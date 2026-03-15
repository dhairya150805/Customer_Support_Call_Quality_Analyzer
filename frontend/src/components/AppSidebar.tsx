import { NavLink as RouterNavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Upload,
  BarChart3,
  Users,
  SlidersHorizontal,
  Settings,
  BrainCircuit,
  PhoneCall,
} from "lucide-react";

const navItems = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Upload Calls", url: "/upload", icon: Upload },
  { title: "Call Insights", url: "/insights", icon: BarChart3 },
  { title: "Agent Performance", url: "/agents", icon: Users },
  { title: "Evaluation Framework", url: "/framework", icon: SlidersHorizontal },
  { title: "Live Analyzer", url: "/live-analyzer", icon: PhoneCall },
  { title: "Settings", url: "/settings", icon: Settings },
];

export function AppSidebar() {
  const location = useLocation();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[260px] bg-sidebar flex flex-col z-30">
      {/* Logo */}
      <div className="h-16 flex items-center gap-2.5 px-5 border-b border-sidebar-border">
        <BrainCircuit className="h-7 w-7 text-primary" />
        <span className="text-lg font-semibold text-sidebar-primary-foreground tracking-tight">
          ReviewSense AI
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.url;
          return (
            <RouterNavLink
              key={item.url}
              to={item.url}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              }`}
            >
              <item.icon className="h-[18px] w-[18px]" />
              <span>{item.title}</span>
            </RouterNavLink>
          );
        })}
      </nav>
    </aside>
  );
}
