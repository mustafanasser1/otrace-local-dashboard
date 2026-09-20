import { useQuery } from "@tanstack/react-query";
import { fetchSummary, type SummaryResult } from "@/lib/api";
import { FALLBACK_SUMMARY } from "@/lib/research-data";

export interface UseSummaryResult extends SummaryResult {
  /** True only when `/ui/api/summary` responded successfully. */
  isLive: boolean;
  /** Honest system status: never claims readiness while the backend is offline. */
  systemStatus: string;
  /** True only when the live backend advertises `capabilities.run`. */
  canRun: boolean;
  isLoading: boolean;
}

export function useSummary(): UseSummaryResult {
  const { data, isLoading } = useQuery({
    queryKey: ["otrace", "summary"],
    queryFn: ({ signal }) => fetchSummary(signal),
    staleTime: 60_000,
    // fetchSummary never throws, so react-query's own retry cannot help here;
    // instead re-check the backend when the tab regains focus or the network
    // comes back, so a temporarily unreachable backend is not pinned as
    // "offline" for the rest of the session.
    retry: false,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
  });


  const result: SummaryResult = data ?? { data: FALLBACK_SUMMARY, source: "fallback" };
  const isLive = result.source === "backend";

  return {
    ...result,
    isLive,
    systemStatus: isLive ? result.data.meta.status : "Backend Offline / Fallback Data",
    canRun: isLive && result.data.capabilities?.run === true,
    isLoading,
  };
}