"use client";

import type { EmployeeDisplay } from "@/types/employee";
import { getStatusConfig } from "@/types/employee";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

interface EmployeeCardProps {
  employee: EmployeeDisplay;
  className?: string;
  onClick?: () => void;
  selected?: boolean;
}

export function EmployeeCard({
  employee,
  className,
  onClick,
  selected,
}: EmployeeCardProps) {
  const isInteractive = Boolean(onClick);
  const statusConfig = getStatusConfig(employee.status);

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
          {employee.specialization && (
            <span className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 font-medium text-muted-foreground">
              {employee.specialization}
            </span>
          )}
          <span className="text-muted-foreground">
            {statusConfig.label}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
