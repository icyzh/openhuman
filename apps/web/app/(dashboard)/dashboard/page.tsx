"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { PlusIcon, SearchIcon, UsersIcon } from "lucide-react";

import { useEmployeesStore } from "@/stores/employees";
import { EmployeeCard } from "@/components/employee-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function DashboardPage() {
  const router = useRouter();
  const employees = useEmployeesStore((s) => s.employees);
  const load = useEmployeesStore((s) => s.load);
  const [search, setSearch] = useState("");

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    if (!search.trim()) return employees;
    const q = search.toLowerCase();
    return employees.filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.role.toLowerCase().includes(q) ||
        e.department.toLowerCase().includes(q) ||
        e.model.toLowerCase().includes(q),
    );
  }, [employees, search]);

  return (
    <div className="flex flex-col gap-6 px-6 py-6">
      <div className="flex flex-col gap-1">
        <p className="text-2xl font-semibold tracking-tight text-foreground">
          Welcome back, vimzh
        </p>
      </div>
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5 shrink-0">
          <UsersIcon className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            Team
          </h1>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {employees.length}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search agents…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-56 h-9 pl-8"
            />
          </div>
          <Button size="lg" onClick={() => router.push("/onboard")}>
            <PlusIcon />
            Add Employee
          </Button>
        </div>
      </div>

      {filtered.length === 0 && employees.length > 0 ? (
        <div className="flex flex-col items-center justify-center py-24">
          <SearchIcon className="size-10 text-muted-foreground/40" />
          <p className="mt-3 text-sm text-muted-foreground">
            No agents match your search.
          </p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24">
          <UsersIcon className="size-10 text-muted-foreground/40" />
          <p className="mt-3 text-sm text-muted-foreground">
            No AI agents deployed yet.
          </p>
          <p className="text-xs text-muted-foreground/60">
            Click &ldquo;Add Employee&rdquo; to deploy your first agent.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((employee) => (
            <EmployeeCard
              key={employee.id}
              employee={employee}
              onClick={() => router.push(`/dashboard/${employee.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
