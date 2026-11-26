import type { Metadata } from "next";

import { PageTitle } from "@/components/features/app-frame/page-title";
import { SettingsContent } from "@/components/features/settings-sections/settings-content";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <>
      <PageTitle>Settings</PageTitle>
      <SettingsContent />
    </>
  );
}
