"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@clerk/nextjs";
import { AgentCarousel } from "@/components/agent-carousel";
import { FlowerDivider } from "@/components/flower-divider";
import { ArrowDiagonal, ArrowRight } from "@/components/ui/button-arrow";

const features = [
  {
    title: "Create a specialist",
    description:
      "Answer 5 questions on the web, name your specialist, define what it does. It joins your server and starts listening. No training, no prompts, no setup.",
  },
  {
    title: "Specialize on anything",
    description:
      "Engineering decisions, sales calls, customer research, recruiting, project management. Give each specialist a focus. The narrower the focus, the sharper it gets.",
  },
  {
    title: "It listens, you ask",
    description:
      "Your specialist reads conversations and joins calls. Ask it anything and get answers with sources: who said what, when, and why.",
  },
  {
    title: "Learns from feedback",
    description:
      "React 👍 or 👎 to its messages and your specialist learns what's actually useful. Over time it gets quieter, sharper, and essential.",
  },
  {
    title: "Onboards like a veteran",
    description:
      "When someone new joins, your specialist catches them up faster than any human can. It was there for every decision, every call, every thread.",
  },
  {
    title: "Self-hosted, open source",
    description:
      "Run it on your own infra. Your data never leaves your server. No SaaS, no subscription, no vendor lock-in.",
  },
];

export default function Home() {
  const { isSignedIn, isLoaded } = useAuth();

  return (
    <main className="flex min-h-screen flex-col items-center">
      <section className="relative flex h-screen w-full flex-col items-center justify-center px-6">
        <h1 className="text-center text-8xl font-base tracking-tight text-foreground">
          Your next favorite AI employee.
        </h1>
        <p className="mt-4 max-w-3xl text-center text-lg leading-relaxed text-muted-foreground">
          Build your own AI coworkers with their own memory. They learn and remember over time,
          handle the boring tasks without complaining, and actually remember what matters
          across every session. Powered by Cognee's memory layer.
        </p>
        <p className="mt-4 text-sm text-muted-foreground/60">
          Powered by{" "}
          <a
            href="https://cognee.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2"
          >
            Cognee
          </a>
        </p>
        <div className="mt-10">
          <Link
            href={isLoaded && isSignedIn ? "/dashboard" : "/sign-up"}
            className="group/button inline-flex items-center gap-3 rounded-lg bg-primary px-10 py-5 text-lg font-medium text-primary-foreground shadow-lg shadow-foreground/10 no-underline"
          >
            {isLoaded && isSignedIn ? "Dashboard" : "Get started"}
            <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      <div className="w-full px-6">
        <div className="mx-auto h-px w-full max-w-7xl bg-gradient-to-r from-transparent via-border to-transparent" />
      </div>

      <AgentCarousel linkTo="/sign-up" />

      <div className="flex w-full justify-center py-12">
        <FlowerDivider width={320} />
      </div>

      <section className="w-full max-w-7xl px-6 pb-24">
        <h2 className="text-center text-7xl font-base tracking-tight text-foreground">
          The Platform
        </h2>
        <div className="mt-12 overflow-hidden rounded-xl border border-border bg-card/40 p-1.5">
          <div className="flex aspect-video w-full items-center justify-center rounded-lg border border-border text-sm text-muted-foreground/40">
            Platform screenshot placeholder
          </div>
        </div>
        <p className="mx-auto mt-16 max-w-lg text-center text-sm leading-relaxed text-muted-foreground/70">
          OpenHuman uses Cognee to power agent memory — giving each specialist persistent context
          across every conversation, call, and thread.
        </p>
        <div className="mt-4 flex justify-center">
          <a
            href="https://cognee.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="group/button inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border border-transparent bg-primary px-2.5 py-2 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/80"
          >
            Cognee
            <ArrowDiagonal />
          </a>
        </div>
      </section>

      <section className="w-full max-w-7xl px-6 pb-24">
        <h2 className="text-center text-8xl font-base tracking-tight text-foreground">
          Get started with 4 premade templates
        </h2>
        <div className="mx-auto mt-12 grid max-w-4xl gap-4 sm:grid-cols-2">
          {[
            {
              name: "Marketing",
              description:
                "Drafts campaigns, monitors brand mentions, and analyzes market trends across every channel.",
              color: "#ef4444",
            },
            {
              name: "Content",
              description:
                "Writes blog posts, documentation, newsletters, and social content in your brand voice.",
              color: "#8b5cf6",
            },
            {
              name: "Support",
              description:
                "Resolves customer issues, escalates edge cases, and keeps your knowledge base up to date.",
              color: "#f59e0b",
            },
            {
              name: "Engineering",
              description:
                "Reviews code, documents architecture decisions, and tracks technical debt across repos.",
              color: "#3b82f6",
            },
          ].map((employee) => (
            <div
              key={employee.name}
              className="rounded-xl border p-1.5"
              style={{
                backgroundColor: `${employee.color}15`,
                borderColor: `${employee.color}30`,
              }}
            >
              <div
                className="flex aspect-[4/3] w-full items-center justify-center rounded-lg text-xs font-medium"
                style={{
                  backgroundColor: `${employee.color}20`,
                  color: `${employee.color}60`,
                }}
              >
                {employee.name}
              </div>
              <div className="mt-2">
                <h3 className="text-base font-semibold text-foreground">{employee.name}</h3>
                <p className="mt-1 text-sm leading-snug text-foreground">{employee.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="w-full max-w-5xl px-6 pb-24">
        <h2 className="text-center text-3xl font-semibold tracking-tight text-foreground">
          How it works
        </h2>
        <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div key={feature.title}>
              <h3 className="text-base font-semibold text-foreground">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>
      <Image
        src="/flower.png"
        alt=""
        width={600}
        height={849}
        className="pointer-events-none absolute bottom-0 right-0 z-10 w-[360px] max-w-none select-none"
      />
    </main>
  );
}
