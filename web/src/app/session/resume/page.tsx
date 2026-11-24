import type { Metadata } from "next";
import { Suspense } from "react";

import { ResumeSession } from "./resume-session";

export const metadata: Metadata = { title: "Restoring session" };

export default function ResumePage() {
  return (
    <main className="flex min-h-svh items-center justify-center px-4">
      <Suspense>
        <ResumeSession />
      </Suspense>
    </main>
  );
}
