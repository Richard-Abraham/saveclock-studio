import { connection } from "next/server";

import { loadSettings } from "@/lib/api/server";

import { DiskWarning } from "../disk-meter-section/disk-warning";
import { LoadError } from "../retry/load-error";
import { SettingsSections } from "./settings-sections";

/** S11 body, read-only. */
export async function SettingsContent() {
  await connection(); // per-request data: never prerendered at build time
  const settings = await loadSettings();
  if (!settings.ok) {
    return (
      <div className="mt-6">
        <LoadError message="We couldn’t load your settings." id="settings-error" error={settings.error} />
      </div>
    );
  }
  return (
    <div className="mt-6 flex flex-col gap-6">
      <DiskWarning volume={settings.data.disk.volume} />
      <SettingsSections settings={settings.data} />
    </div>
  );
}
