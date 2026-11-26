import type { ProjectList, SettingsOut } from "@saveclock/contracts";

import { readServerEnv } from "../server-env";
import { createApi } from "./client";
import { getProjects, getSettings } from "./endpoints";
import { ApiError } from "./errors";

/** Server components fetch through here, straight to the API (never back through the rewrite). */
export type Loaded<T> = { ok: true; data: T } | { ok: false; error: ApiError };

async function load<T>(run: () => Promise<T>): Promise<Loaded<T>> {
  try {
    return { ok: true, data: await run() };
  } catch (cause) {
    if (cause instanceof ApiError) return { ok: false, error: cause };
    throw cause;
  }
}

const serverApi = () => createApi(readServerEnv().apiOrigin, { noStore: true });

export const loadSettings = (): Promise<Loaded<SettingsOut>> => load(() => getSettings(serverApi()));

export const loadProjects = (): Promise<Loaded<ProjectList>> => load(() => getProjects(serverApi()));
