import { fetchMetrics } from "../lib/api";

export function useMetrics() {
  return fetchMetrics();
}
