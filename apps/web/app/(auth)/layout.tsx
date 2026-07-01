import Link from "next/link";
import { Suspense } from "react";

import { Logo } from "@/components/logo";
import { Spinner } from "@/components/ui/spinner";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-svh items-center justify-center bg-background-app px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <Link
          href="/"
          className="flex items-center justify-center gap-1.5 no-underline"
        >
          <Logo className="h-6 w-6" />
          <span className="text-lg font-semibold tracking-tight text-foreground">
            OpenHuman
          </span>
        </Link>
        <Suspense fallback={<Spinner />}>{children}</Suspense>
      </div>
    </div>
  );
}
