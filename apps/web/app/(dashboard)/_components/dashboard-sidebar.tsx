"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useClerk } from "@clerk/nextjs";
import {
  Activity,
  BookOpen,
  Building2,
  HardDrive,
  LayoutDashboard,
  LogOut,
  Puzzle,
  Settings,
} from "lucide-react";

import { Logo } from "@/components/logo";
import { useOrgStore } from "@/stores/org";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Activity", href: "/activity", icon: Activity },
  { label: "Storage", href: "/storage", icon: HardDrive },
  { label: "MCP Marketplace", href: "/mcp-marketplace", icon: Puzzle },
  { label: "Organization", href: "/organization", icon: Building2 },
  { label: "Documentation", href: "/docs", icon: BookOpen },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function DashboardSidebar() {
  const pathname = usePathname();
  const { signOut } = useClerk();
  const clearOrg = useOrgStore((s) => s.clearOrg);

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

      <SidebarFooter>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip="Logout"
                  onClick={() => {
                    clearOrg();
                    signOut({ redirectUrl: "/" });
                  }}
                >
                  <LogOut />
                  <span>Logout</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarFooter>
    </Sidebar>
  );
}
