// THROWAWAY: dev-only driver (ROADMAP T-2.13). Delete when the Phase 3 screens exist.
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageTitle } from "@/components/features/app-frame/page-title";
import { DevDriver } from "@/components/features/dev-driver/dev-driver";
import { readServerEnv } from "@/lib/server-env";

export const metadata: Metadata = { title: "Developer driver" };
// Read the flag per request: without this Next would evaluate it at build time and bake it in.
export const dynamic = "force-dynamic";

export default function DevPage() {
  if (!readServerEnv().devDriver) notFound();
  return (
    <>
      <PageTitle>Developer driver</PageTitle>
      <DevDriver />
    </>
  );
}
