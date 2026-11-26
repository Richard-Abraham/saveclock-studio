import { connection } from "next/server";

/** Liveness of the web server itself (ARCH §14); not part of /api/v1. */
export async function GET(): Promise<Response> {
  await connection();
  return new Response("ok", {
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
  });
}
