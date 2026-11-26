import type { Metadata } from "next";
import Link from "next/link";

import { PageTitle } from "@/components/features/app-frame/page-title";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <>
      <PageTitle>We can’t find that page.</PageTitle>
      <p className="mt-4">
        <Link href="/" className="link inline-flex min-h-11 items-center">
          Go to Projects
        </Link>
      </p>
    </>
  );
}
