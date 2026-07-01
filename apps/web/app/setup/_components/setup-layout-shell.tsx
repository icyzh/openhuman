"use client";

import Link from "next/link";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth";
import { useOrgStore } from "@/stores/org";

export function SetupLayoutShell({ children }: { children: React.ReactNode }) {
  const { logout, user } = useAuthStore();
  const clearOrg = useOrgStore((s) => s.clearOrg);

  const handleSignOut = () => {
    clearOrg();
    logout();
  };

  return (
    <div className="relative flex min-h-svh flex-col bg-background-app">
      <div className="absolute right-4 top-4 flex items-center gap-3">
        {user && (
          <span className="text-sm text-muted-foreground">{user.email}</span>
        )}
        <Button variant="outline" size="sm" onClick={handleSignOut}>
          Sign out
        </Button>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-lg space-y-8">
          <Link
            href="/"
            className="flex items-center justify-center gap-1.5 no-underline"
          >
            <Logo className="h-6 w-6" />
            <span className="text-lg font-semibold tracking-tight text-foreground">
              OpenHuman
            </span>
          </Link>
          {children}
        </div>
      </div>
    </div>
  );
}
