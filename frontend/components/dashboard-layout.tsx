"use client"

import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"
import { Separator } from "@/components/ui/separator"

interface DashboardLayoutProps {
  children: React.ReactNode
  breadcrumb?: React.ReactNode
}

export function DashboardLayout({ children, breadcrumb }: DashboardLayoutProps) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="bg-background/50">
        <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-3 border-b border-border/50 bg-background/80 px-6 backdrop-blur-xl">
          <SidebarTrigger className="-ml-1 size-9 rounded-lg border border-border/50 bg-card/50 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground" />
          {breadcrumb && (
            <>
              <Separator orientation="vertical" className="mr-2 h-5 bg-border/50" />
              {breadcrumb}
            </>
          )}
        </header>
        <main className="flex-1 overflow-auto p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">
            {children}
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
