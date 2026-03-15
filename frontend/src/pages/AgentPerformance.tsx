import { DashboardLayout } from "@/components/DashboardLayout";
import { AgentTable } from "@/components/AgentTable";

const AgentPerformance = () => {
  return (
    <DashboardLayout>
      <div className="mb-6">
        <h1 className="text-[28px] font-semibold text-foreground tracking-tight">Agent Performance</h1>
        <p className="text-sm text-muted-foreground mt-1">Monitor and compare agent quality metrics</p>
      </div>
      <AgentTable />
    </DashboardLayout>
  );
};

export default AgentPerformance;
