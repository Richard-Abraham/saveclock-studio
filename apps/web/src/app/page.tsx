import type { Metadata } from "next";
import { Suspense } from "react";

import { PageTitle } from "@/components/features/app-frame/page-title";
import { ProjectsContent } from "@/components/features/project-list/projects-content";
import { ProjectsSkeleton } from "@/components/features/project-list/projects-skeleton";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  return (
    <>
      <PageTitle>Projects</PageTitle>
      <Suspense fallback={<ProjectsSkeleton />}>
        <ProjectsContent />
      </Suspense>
    </>
  );
}
