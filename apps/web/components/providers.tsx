"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { useAuthStore } from "@/stores/auth";

interface ProvidersProps {
  readonly children: ReactNode;
}

function AuthInitializer({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const initialize = useAuthStore((s) => s.initialize);
  const token = useAuthStore((s) => s.token);
  const isLoading = useAuthStore((s) => s.isLoading);
  const hadTokenRef = useRef(!!token);

  useEffect(() => {
    hadTokenRef.current = !!token;
  }, [token]);

  useEffect(() => {
    initialize();
  }, [initialize]);

  // Redirect to /login if we had a token that just got cleared (expired/invalid)
  useEffect(() => {
    if (
      !isLoading &&
      hadTokenRef.current &&
      token === null &&
      (pathname.startsWith("/dashboard") ||
        pathname.startsWith("/setup") ||
        pathname.startsWith("/onboard") ||
        pathname.startsWith("/organization") ||
        pathname.startsWith("/activity") ||
        pathname.startsWith("/storage") ||
        pathname.startsWith("/settings"))
    ) {
      router.push("/login");
    }
  }, [isLoading, token, pathname, router]);

  return <>{children}</>;
}

export const Providers = ({ children }: ProvidersProps) => {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthInitializer>
        <TooltipProvider>
          {children}
          <Toaster />
        </TooltipProvider>
      </AuthInitializer>
    </QueryClientProvider>
  );
};
