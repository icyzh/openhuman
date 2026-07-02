"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSignIn } from "@clerk/nextjs";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { Logo } from "@/components/logo";

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

export function SignInForm() {
  const router = useRouter();
  const { signIn, fetchStatus } = useSignIn();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!signIn || fetchStatus === "fetching") {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner />
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const { error } = await signIn.create({
        identifier,
        password,
      });

      if (error) {
        toast.error(error.longMessage || error.message || "Sign-in failed.");
        return;
      }

      if (signIn.status === "complete" && signIn.createdSessionId) {
        await signIn.finalize({ navigate: () => router.push("/dashboard") });
        return;
      }

      // Handle other statuses (MFA, etc.)
      toast.error("Additional verification required. Please contact support.");
    } catch (err: unknown) {
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message: string }> };
      const msg = clerkErr?.errors?.[0]?.longMessage || clerkErr?.errors?.[0]?.message || "Sign-in failed.";
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOAuth(strategy: "oauth_google" | "oauth_github") {
    try {
      await signIn.sso({
        strategy,
        redirectUrl: "/dashboard",
        redirectCallbackUrl: "/sso-callback",
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "OAuth sign-in failed.";
      toast.error(message);
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm space-y-6">
      {/* Branding */}
      <div className="flex flex-col items-center gap-1.5">
        <Logo className="h-8 w-8 text-primary" />
        <h1 className="font-heading text-xl font-semibold text-foreground">
          Welcome back
        </h1>
        <p className="text-sm text-muted-foreground">
          Sign in to your OpenHuman account
        </p>
      </div>

      {/* OAuth buttons */}
      <div className="space-y-2.5">
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => handleOAuth("oauth_google")}
          className="group relative flex w-full items-center justify-center gap-2.5 rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-foreground transition-all hover:border-[#4285F4]/40 hover:bg-[#4285F4]/[0.04] hover:shadow-sm active:translate-y-px disabled:pointer-events-none disabled:opacity-50 dark:bg-[#1a1717] dark:hover:bg-[#4285F4]/[0.08]"
        >
          <GoogleIcon className="size-4 transition-transform group-hover:scale-110" />
          Continue with Google
        </button>
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => handleOAuth("oauth_github")}
          className="group relative flex w-full items-center justify-center gap-2.5 rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-foreground transition-all hover:border-foreground/30 hover:bg-foreground/[0.04] hover:shadow-sm active:translate-y-px disabled:pointer-events-none disabled:opacity-50 dark:bg-[#1a1717] dark:hover:bg-foreground/[0.06] dark:hover:border-foreground/20"
        >
          <GitHubIcon className="size-4 transition-transform group-hover:scale-110" />
          Continue with GitHub
        </button>
      </div>

      {/* Divider */}
      <div className="relative">
        <Separator />
        <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-background-app px-2 text-xs text-muted-foreground">
          or continue with email
        </span>
      </div>

      {/* Email sign-in form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="identifier">
            Email address <span className="text-destructive">*</span>
          </Label>
          <Input
            id="identifier"
            type="email"
            placeholder="you@example.com"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            disabled={isSubmitting}
            required
          />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">
              Password <span className="text-destructive">*</span>
            </Label>
            <Link
              href="/sign-in/forgot-password"
              className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              Forgot password?
            </Link>
          </div>
          <Input
            id="password"
            type="password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isSubmitting}
            required
          />
        </div>

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Spinner className="mr-2 size-3.5" />}
          Sign in
        </Button>
      </form>

      {/* Sign-up link */}
      <p className="text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{" "}
        <Link
          href="/sign-up"
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Create one
        </Link>
      </p>
    </div>
  );
}
