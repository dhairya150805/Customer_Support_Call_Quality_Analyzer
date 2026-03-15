import { DashboardLayout } from "@/components/DashboardLayout";

const SettingsPage = () => {
  return (
    <DashboardLayout>
      <div className="mb-6">
        <h1 className="text-[28px] font-semibold text-foreground tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your account and preferences</p>
      </div>
      <div className="chart-card max-w-2xl">
        <p className="text-sm text-muted-foreground">Settings page coming soon.</p>
      </div>
    </DashboardLayout>
  );
};

export default SettingsPage;
