/** Host allowlist helpers (SEC-166, plan 002 W14). Pure: shared by `proxy.ts` and `next.config.ts`. */

/** `localhost:3000` -> `localhost`; `[::1]:3000` -> `::1`; lowercase, no trailing dot. */
export function hostname(hostHeader: string): string {
  let host = hostHeader.trim().toLowerCase();
  if (host.startsWith("[")) {
    host = host.slice(1).split("]", 1)[0] ?? "";
  } else if (host.split(":").length === 2) {
    host = host.split(":", 1)[0] ?? "";
  }
  return host.replace(/\.$/, "");
}

export function parseAllowedHosts(csv: string): string[] {
  return csv
    .split(",")
    .map((h) => h.trim().toLowerCase().replace(/\.$/, ""))
    .filter((h) => h !== "");
}

/** A missing or empty Host is never allowed. */
export function isAllowedHost(hostHeader: string | null | undefined, allowed: readonly string[]): boolean {
  if (hostHeader == null || hostHeader.trim() === "") return false;
  return allowed.includes(hostname(hostHeader));
}
