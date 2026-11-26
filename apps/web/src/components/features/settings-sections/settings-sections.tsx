import type { SettingsOut } from "@saveclock/contracts";

import { StatusPill } from "@/components/ui";

import { DiskMeter } from "../disk-meter-section/disk-meter";
import { SettingRow, SettingsSection } from "./settings-section";

const NBSP = " ";

function KeyStatus({ configured, missing }: { configured: boolean; missing: "warn" | "neutral" }) {
  if (configured) {
    return (
      <StatusPill tone="lock" icon="check">
        Set
      </StatusPill>
    );
  }
  return missing === "warn" ? (
    <StatusPill tone="warn" icon="triangle-alert">
      Not set
    </StatusPill>
  ) : (
    <StatusPill tone="neutral" icon="minus">
      Not set
    </StatusPill>
  );
}

function EnvName({ children }: { children: string }) {
  return <span translate="no">{children}</span>;
}

function ApiKeys({ keys, pixabayEnabled }: { keys: SettingsOut["keys"]; pixabayEnabled: boolean }) {
  return (
    <SettingsSection title="API keys" id="api-keys">
      <dl className="flex flex-col gap-3">
        <SettingRow
          label="Pexels"
          help={
            keys.pexels.configured ? null : (
              <>
                Pexels isn’t set up, so no clips can be fetched. Set <EnvName>PEXELS_API_KEY</EnvName> in the
                server environment.
              </>
            )
          }
        >
          <KeyStatus configured={keys.pexels.configured} missing="warn" />
        </SettingRow>
        <SettingRow
          label="Pixabay"
          help={
            !keys.pixabay.configured && pixabayEnabled ? (
              <>
                Set <EnvName>PIXABAY_API_KEY</EnvName> in the server environment.
              </>
            ) : null
          }
        >
          <KeyStatus configured={keys.pixabay.configured} missing="neutral" />
        </SettingRow>
        <SettingRow
          label="Claude"
          help={keys.anthropic.configured ? null : "Optional — Claude Code can set keywords instead."}
        >
          <KeyStatus configured={keys.anthropic.configured} missing="neutral" />
        </SettingRow>
      </dl>
      <p className="text-small text-ink-muted">Keys live in the server environment.</p>
    </SettingsSection>
  );
}

function StockSources({ stock }: { stock: SettingsOut["stock"] }) {
  return (
    <SettingsSection title="Stock sources" id="stock-sources">
      <dl className="flex flex-col gap-3">
        <SettingRow label="Pexels (primary)">Always on</SettingRow>
        <SettingRow label="Also use Pixabay">{stock.pixabay_enabled ? "On" : "Off"}</SettingRow>
      </dl>
    </SettingsSection>
  );
}

function Storage({ settings }: { settings: SettingsOut }) {
  const days = settings.intermediate_ttl_days;
  return (
    <SettingsSection title="Storage" id="storage">
      <DiskMeter volume={settings.disk.volume} />
      <p className="text-small text-ink-muted">
        Intermediates (raw clips, proxies) are cleaned up {days}
        {NBSP}
        {days === 1 ? "day" : "days"} after last use. Songs and videos stay until you delete the project.
      </p>
    </SettingsSection>
  );
}

function Performance({ tuning }: { tuning: SettingsOut["tuning"] }) {
  return (
    <SettingsSection title="Performance" id="performance">
      {tuning === null ? (
        <p className="text-ink-muted">Not available: the worker isn’t running</p>
      ) : (
        <>
          <p className="text-small text-ink-muted">Detected when the worker started. Change them in .env.</p>
          <dl className="flex flex-col gap-3">
            <SettingRow label="Heavy-job concurrency">{tuning.heavy}</SettingRow>
            <SettingRow label="FFmpeg threads">{tuning.ffmpeg_threads}</SettingRow>
            <SettingRow label="Torch threads">{tuning.torch_threads}</SettingRow>
            <SettingRow label="Fetch concurrency">{tuning.fetch_concurrency}</SettingRow>
            <SettingRow label="Device">
              <span translate="no">{tuning.device}</span>
            </SettingRow>
          </dl>
        </>
      )}
    </SettingsSection>
  );
}

/** S11, read-only: no input, select, textarea or button, and only fields named here are rendered. */
export function SettingsSections({ settings }: { settings: SettingsOut }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2 lg:gap-6">
      <ApiKeys keys={settings.keys} pixabayEnabled={settings.stock.pixabay_enabled} />
      <StockSources stock={settings.stock} />
      <Storage settings={settings} />
      <Performance tuning={settings.tuning} />
    </div>
  );
}
