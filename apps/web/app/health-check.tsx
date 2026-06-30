"use client";

import { useHealthHealthCheck } from "@repo/api-client";

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
};

export const HealthCheck = () => {
  const { data, isLoading, isError, error } = useHealthHealthCheck();

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <h2 className="mb-4 text-lg font-medium">API Health</h2>
      {isLoading && (
        <p className="text-zinc-500">Checking API status...</p>
      )}
      {isError && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          Failed to connect: {getErrorMessage(error)}
        </div>
      )}
      {data && (
        <div className="flex items-center gap-2">
          <span className="inline-flex h-2 w-2 rounded-full bg-green-500" />
          <span className="text-sm text-zinc-600 dark:text-zinc-400">
            Status: {data.status} (v{data.version})
          </span>
        </div>
      )}
    </div>
  );
};
