"use client";

import { useState } from "react";

import { Button, Callout, Card, StatusPill } from "@/components/ui";
import { createApi } from "@/lib/api/client";
import { directApiBase } from "@/lib/api/direct";
import {
  createProject,
  downloadUrl,
  KIND_LABEL,
  requestModeA,
  startRender,
  uploadSong,
  type DownloadKind,
  type DriverInput,
} from "@/lib/api/driver";
import { ApiError } from "@/lib/api/errors";

import { useProjectEvents } from "./use-project-events";

const FIELD = "min-h-11 rounded-control border border-line-strong bg-surface-2 px-3 text-ink";

function message(cause: unknown): string {
  return cause instanceof ApiError ? `${cause.code}: ${cause.message}` : "Something unexpected went wrong.";
}

/** Throwaway dev driver (ROADMAP T-2.13): upload, generate, download. Every call goes to the API's own origin. */
export function DevDriver() {
  const [api] = useState(() => createApi(directApiBase()));
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState<DriverInput>({ vibe: "", keywords: "", duration: 30 });
  const [projectId, setProjectId] = useState<string | null>(null);
  const [renderId, setRenderId] = useState<string | null>(null);
  const [reopen, setReopen] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const events = useProjectEvents(projectId, reopen);

  async function run(step: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await step();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  function generate() {
    if (!file) return;
    void run(async () => {
      const project = await createProject(api, form);
      await uploadSong(api, project.id, file);
      setProjectId(project.id);
      setRenderId(null);
    });
  }

  const canRender = projectId !== null && (events.status === "draft" || events.status === "ready");

  return (
    <div className="mt-4 flex flex-col gap-6">
      <Callout variant="warn" title="Developer driver">
        A throwaway page for trying the pipeline before the real editor exists. It is served only when the
        developer flag is on.
      </Callout>

      <Card className="p-4">
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
          }}
        >
          <label className="flex flex-col gap-1">
            <span className="font-medium">Song</span>
            <input
              type="file"
              accept="audio/*"
              className={FIELD}
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
              }}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-medium">Vibe</span>
            <input
              className={FIELD}
              value={form.vibe}
              maxLength={200}
              onChange={(event) => {
                setForm({ ...form, vibe: event.target.value });
              }}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-medium">Keywords (comma separated, optional)</span>
            <input
              className={FIELD}
              value={form.keywords}
              onChange={(event) => {
                setForm({ ...form, keywords: event.target.value });
              }}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-medium">Length</span>
            <select
              className={FIELD}
              value={form.duration}
              onChange={(event) => {
                setForm({ ...form, duration: Number(event.target.value) as DriverInput["duration"] });
              }}
            >
              <option value={15}>15 seconds</option>
              <option value={30}>30 seconds</option>
              <option value={60}>60 seconds</option>
            </select>
          </label>
          <div>
            <Button disabled={!file} loading={busy} loadingLabel="Working…" onClick={generate}>
              Generate
            </Button>
          </div>
        </form>
      </Card>

      {error ? (
        <Callout variant="danger" title="That did not work">
          {error}
        </Callout>
      ) : null}

      {projectId ? (
        <Card className="flex flex-col gap-4 p-4">
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill tone="neutral" icon="loader">
              {events.status ?? "waiting"}
            </StatusPill>
            <span className="text-small text-ink-muted">Project {projectId}</span>
          </div>
          <ul aria-label="Progress" role="status" className="text-small">
            {events.lines.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-3">
            <Button
              disabled={!canRender || busy}
              onClick={() => {
                void run(async () => {
                  const started = await startRender(api, projectId);
                  setRenderId(started.render_id);
                  setReopen((n) => n + 1);
                });
              }}
            >
              Render
            </Button>
            <Button
              disabled={!events.readyRender || busy}
              onClick={() => {
                void run(async () => {
                  if (events.readyRender) await requestModeA(api, events.readyRender);
                  setReopen((n) => n + 1);
                });
              }}
            >
              Mode A
            </Button>
          </div>
          {events.readyRender || renderId ? (
            <ul className="flex flex-col gap-1">
              {(Object.keys(KIND_LABEL) as DownloadKind[]).map((kind) =>
                kind === "with_song" && !events.modeAReady ? null : (
                  <li key={kind}>
                    <a className="link" href={downloadUrl(events.readyRender ?? renderId ?? "", kind)}>
                      {KIND_LABEL[kind]}
                    </a>
                  </li>
                ),
              )}
            </ul>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
