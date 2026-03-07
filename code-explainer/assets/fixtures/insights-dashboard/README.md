# Insights Dashboard

Insights Dashboard is a lightweight React application for viewing product KPIs.
The app is organized around pages, reusable components, hooks, and a small API client.

## Structure

- `src/main.tsx` mounts the application.
- `src/App.tsx` wires the dashboard page.
- `src/pages/Dashboard.tsx` coordinates KPI cards.
- `src/hooks/useMetrics.ts` fetches metrics through `src/lib/api.ts`.
- `src/components/KpiCard.tsx` renders reusable metric tiles.
