import type { UiStatus } from "@saveclock/contracts";

import type { IconName, PillTone } from "@/components/ui";

type PillSpec = { label: string; tone: PillTone; icon: IconName };

/** Pill copy per status (UX-SPEC S9, ARCH §4). A status added in Python breaks `tsc` until mapped. */
export const STATUS_PILL = {
  uploading: { label: "Uploading…", tone: "neutral", icon: "clock" },
  analysing: { label: "Analysing…", tone: "neutral", icon: "clock" },
  draft: { label: "Draft", tone: "neutral", icon: "file" },
  rendering: { label: "Rendering…", tone: "neutral", icon: "clock" },
  ready: { label: "Ready", tone: "lock", icon: "check" },
  failed: { label: "Failed", tone: "danger", icon: "circle-alert" },
  canceled: { label: "Cancelled", tone: "neutral", icon: "ban" },
} satisfies Record<UiStatus, PillSpec>;
