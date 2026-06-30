"use client";

import type { Employee } from "@/data/employees";
import { DEPARTMENT_COLORS } from "@/data/employees";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

interface EmployeeCardProps {
  employee: Employee;
  className?: string;
  onClick?: () => void;
  selected?: boolean;
}

const STATUS_CONFIG: Record<
  Employee["status"],
  { label: string; dotColor: string }
> = {
  active: { label: "Working", dotColor: "bg-green-500" },
  training: { label: "Working", dotColor: "bg-green-500" },
  idle: { label: "Idle", dotColor: "bg-amber-400" },
  offline: { label: "Idle", dotColor: "bg-muted-foreground/30" },
};

export function EmployeeCard({
  employee,
  className,
  onClick,
  selected,
}: EmployeeCardProps) {
  const isInteractive = Boolean(onClick);
  const deptColor = DEPARTMENT_COLORS[employee.department] ?? "#6b7280";
  const statusConfig = STATUS_CONFIG[employee.status];

  return (
    <Card
      className={cn(
        "group/employee",
        isInteractive && "cursor-pointer transition-shadow hover:shadow-md",
        selected && "ring-2 ring-primary",
        className,
      )}
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter") onClick();
            }
          : undefined
      }
      role={isInteractive ? "button" : undefined}
      tabIndex={isInteractive ? 0 : undefined}
    >
      <CardContent>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-block size-2 shrink-0 rounded-full",
              statusConfig.dotColor,
            )}
          />
          <h3 className="truncate text-base font-semibold text-foreground">
            {employee.name}
          </h3>
        </div>

        <p className="mt-0.5 text-sm text-muted-foreground">
          {employee.role}
        </p>

        <div className="mt-2 flex items-center gap-2 text-xs">
          <span
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-medium"
            style={{
              backgroundColor: `${deptColor}12`,
              color: deptColor,
            }}
          >
            {employee.department}
          </span>
          <span className="text-muted-foreground">
            {statusConfig.label}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
