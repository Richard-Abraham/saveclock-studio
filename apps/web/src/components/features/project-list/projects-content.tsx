import Link from "next/link";
import { connection } from "next/server";

import { loadProjects, loadSettings } from "@/lib/api/server";

import { DiskMeter } from "../disk-meter-section/disk-meter";
import { DiskWarning } from "../disk-meter-section/disk-warning";
import { LoadError } from "../retry/load-error";
import { ProjectList } from "./project-list";

/** S9 body: disk usage and the project list. Either request failing is one failure, one Retry. */
export async function ProjectsContent() {
  await connection(); // per-request data: never prerendered at build time
  const [projects, settings] = await Promise.all([loadProjects(), loadSettings()]);

  if (!projects.ok || !settings.ok) {
    const error = projects.ok ? (settings.ok ? null : settings.error) : projects.error;
    return error ? (
      <div className="mt-6">
        <LoadError message="We couldn’t load your projects." id="projects-error" error={error} />
      </div>
    ) : null;
  }

  const { volume } = settings.data.disk;
  // shortcut: first page only, add paging when the list exceeds one page (Phase 3)
  const items = projects.data.items;
  return (
    <div className="mt-4 flex flex-col gap-6">
      <div className="lg:w-[calc((100%-2rem)/3)]">
        <DiskMeter
          volume={volume}
          trailing={
            <>
              <span aria-hidden="true"> · </span>
              <Link href="/settings#storage" className="link">
                Manage storage
              </Link>
            </>
          }
        />
      </div>
      <DiskWarning volume={volume} />
      <ProjectList items={items} />
    </div>
  );
}
