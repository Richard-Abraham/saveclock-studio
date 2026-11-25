# ADR-0014: Local-only edition (no VPS, no Tailscale)

- Status: accepted (owner directive, DECISIONS Rev 3.5 §8f)
- Date: 2026-11-26
- Deciders: project owner
- Supersedes (in part): ADR-0012 (access via Tailscale on the VPS). ADR-0012 stays as the recipe if phone access is wanted later.
- Related: DECISIONS §3, §6, §8c, §8f; ADR-0013

## Context and problem statement
The owner will run SaveClock Studio on their own capable machine and use it only there. A VPS and a private network were planned to give always-on rendering and phone access, which the owner no longer needs. Removing them cuts moving parts, accounts and cost.

## Decision
Run the Compose stack locally. Bind every port to `127.0.0.1`. Because a login-free local app can still be reached from other sites open in the same browser, the API rejects any `Host` other than `localhost`/`127.0.0.1` and any state-changing request whose `Origin` is not the app's own. The owner uses the app through Claude Code: a thin `saveclock` CLI over the same local API sits alongside the web editor. Claude Code supplies the clip keywords through the CLI, so no API key is needed. Haiku is used only if a key is set; otherwise the offline table is the fallback.

## Consequences
- Good: no server, no tailnet, no keys required, nothing reachable from the network.
- Bad: no phone access and no rendering while the machine is off. Speed targets are measured on the owner's hardware, not a reference server.
- Neutral: the `user_id` seams and the `BlobStore` adapter are unchanged, so the Phase P path is the same.
