"use client";

import { ActivityIcon } from "lucide-react";

export default function ActivityPage() {
  return (
    <div className="flex flex-col gap-6 px-6 py-6">
      <div className="flex items-center gap-2.5">
        <ActivityIcon className="size-5 text-muted-foreground" />
        <h1 className="text-lg font-semibold tracking-tight text-foreground">
          Activity
        </h1>
      </div>

      <div className="flex flex-col items-center justify-center py-24">
        <ActivityIcon className="size-10 text-muted-foreground/40" />
        <p className="mt-3 text-sm text-muted-foreground">
          No recent activity.
        </p>
      </div>
    </div>
  );
}
