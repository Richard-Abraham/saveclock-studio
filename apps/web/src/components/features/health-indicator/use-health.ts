"use client";

import { useQuery } from "@tanstack/react-query";

import { browserApi } from "@/lib/api/browser";
import { fetchHealth } from "@/lib/api/endpoints";

export const HEALTH_KEY = ["health"] as const;

/** Polls /health/ready every 15 s, never retries (so "unreachable" shows within one poll), and
 *  stops while the tab is hidden (refetchIntervalInBackground defaults to false). */
export function useHealth() {
  return useQuery({
    queryKey: HEALTH_KEY,
    queryFn: () => fetchHealth(browserApi),
    refetchInterval: 15_000,
    retry: false,
  });
}
