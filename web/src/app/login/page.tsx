import type { Metadata } from "next";
import { TruckIcon } from "lucide-react";
import { Suspense } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

const NOTICES: Record<string, string> = {
  expired: "Your session expired. Sign in again.",
};

async function LoginFormWithNotice({ searchParams }: PageProps<"/login">) {
  const { reason } = await searchParams;
  const notice = typeof reason === "string" ? NOTICES[reason] : undefined;
  return <LoginForm notice={notice} />;
}

export default function LoginPage(props: PageProps<"/login">) {
  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 px-4 py-12">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <div className="mx-auto mb-2 flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <TruckIcon className="size-6" aria-hidden="true" />
          </div>
          <CardTitle className="text-xl">Fleet Manager</CardTitle>
          <CardDescription>Vehicles, drivers, maintenance and costs in one place.</CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<LoginForm />}>
            <LoginFormWithNotice {...props} />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  );
}
