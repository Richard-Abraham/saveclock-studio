import type { Metadata } from "next";
import { Suspense } from "react";

import { PageTitle } from "@/components/features/app-frame/page-title";
import { SettingsContent } from "@/components/features/settings-sections/settings-content";
import { SettingsSkeleton } from "@/components/features/settings-sections/settings-skeleton";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <>
      <PageTitle>Settings</PageTitle>
      <Suspense fallback={<SettingsSkeleton />}>
        <SettingsContent />
      </Suspense>
    </>
  );
}
