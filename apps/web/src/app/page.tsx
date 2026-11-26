import type { Metadata } from "next";

import { PageTitle } from "@/components/features/app-frame/page-title";
import { ProjectsContent } from "@/components/features/project-list/projects-content";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  return (
    <>
      <PageTitle>Projects</PageTitle>
      <ProjectsContent />
    </>
  );
}
