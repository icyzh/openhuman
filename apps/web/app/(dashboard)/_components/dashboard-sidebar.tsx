"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  Building2,
  HardDrive,
  LayoutDashboard,
  Settings,
} from "lucide-react";

import { Logo } from "@/components/logo";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Activity", href: "/activity", icon: Activity },
  { label: "Storage", href: "/storage", icon: HardDrive },
  { label: "Organization", href: "/organization", icon: Building2 },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function DashboardSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar>
      <SidebarHeader>
        <Link
          href="/"
          className="flex items-center justify-center gap-1.5 px-2 pt-1 text-lg font-semibold tracking-tight text-sidebar-foreground no-underline group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:pt-0"
        >
          <span className="group-data-[collapsible=icon]:hidden">Open</span>
          <Logo className="h-6 w-6 shrink-0 text-sidebar-foreground" />
          <span className="group-data-[collapsible=icon]:hidden">Human</span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              {NAV_ITEMS.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    isActive={pathname === item.href}
                    tooltip={item.label}
                    render={<Link href={item.href} />}
                  >
                    <item.icon />
                    <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
