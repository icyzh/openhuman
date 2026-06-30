"use client";

import { Building2Icon } from "lucide-react";

export default function OrganizationPage() {
  return (
    <div className="flex flex-col gap-6 px-6 py-6">
      <div className="flex items-center gap-2.5">
        <Building2Icon className="size-5 text-muted-foreground" />
        <h1 className="text-lg font-semibold tracking-tight text-foreground">
          Organization
        </h1>
      </div>

      <div className="flex flex-col items-center justify-center py-24">
        <Building2Icon className="size-10 text-muted-foreground/40" />
        <p className="mt-3 text-sm text-muted-foreground">
          No organization members yet.
        </p>
      </div>
    </div>
  );
}
