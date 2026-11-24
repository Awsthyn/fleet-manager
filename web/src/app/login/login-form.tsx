"use client";

import { Loader2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

type Pending = "password" | "demo" | null;

async function signIn(endpoint: string, body?: FormData): Promise<string | null> {
  try {
    const response = await fetch(endpoint, { method: "POST", body });
    if (response.ok) return null;
    const data = (await response.json().catch(() => ({}))) as { error?: string };
    return data.error ?? "Sign-in failed.";
  } catch {
    return "Network error. Check your connection.";
  }
}

export function LoginForm({ notice }: { notice?: string }) {
  const router = useRouter();
  const [pending, setPending] = useState<Pending>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(kind: Exclude<Pending, null>, endpoint: string, body?: FormData) {
    setPending(kind);
    setError(null);
    const failure = await signIn(endpoint, body);
    if (failure) {
      setError(failure);
      setPending(null);
      return;
    }
    router.replace("/");
    router.refresh();
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run("password", "/api/auth/login", new FormData(event.currentTarget));
  }

  return (
    <div className="flex flex-col gap-5">
      {notice && !error ? (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      ) : null}
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <Button
        size="lg"
        className="h-11 w-full text-base"
        disabled={pending !== null}
        onClick={() => void run("demo", "/api/auth/demo")}
      >
        {pending === "demo" ? <Loader2Icon className="animate-spin" aria-hidden="true" /> : null}
        Try the demo
      </Button>
      <p className="-mt-3 text-center text-xs text-muted-foreground">
        Read-only access with fictional data. No sign-up needed.
      </p>

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <Separator className="flex-1" />
        or sign in
        <Separator className="flex-1" />
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" name="email" type="email" autoComplete="username" required />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </div>
        <Button type="submit" variant="outline" size="lg" disabled={pending !== null}>
          {pending === "password" ? (
            <Loader2Icon className="animate-spin" aria-hidden="true" />
          ) : null}
          Sign in
        </Button>
      </form>
    </div>
  );
}
