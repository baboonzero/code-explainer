import { KpiCard } from "../components/KpiCard";
import { useMetrics } from "../hooks/useMetrics";

export function DashboardPage() {
  const metrics = useMetrics();
  return (
    <main>
      <h1>Insights Dashboard</h1>
      {metrics.map((metric) => (
        <KpiCard key={metric.label} label={metric.label} value={metric.value} />
      ))}
    </main>
  );
}
