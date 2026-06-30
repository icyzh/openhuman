import { HealthCheck } from "./health-check";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 dark:bg-black">
      <main className="flex flex-col items-center gap-8">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          OpenHuman
        </h1>
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          AI-powered human simulation platform
        </p>
        <HealthCheck />
      </main>
    </div>
  );
}
