import { DashboardLayout } from "@/components/dashboard-layout"
import { CurrentStrategyCard } from "@/components/dashboard/current-strategy-card"
import { ResearchLoopCard } from "@/components/dashboard/research-loop-card"
import { RecentExperimentsCard } from "@/components/dashboard/recent-experiments-card"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb"

export default function DashboardPage() {
  return (
    <DashboardLayout
      breadcrumb={
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbPage className="text-sm font-medium">Dashboard</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      }
    >
      <div className="flex flex-col gap-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
          <p className="text-sm text-muted-foreground">Monitor your strategy performance and research progress</p>
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <CurrentStrategyCard />
          <ResearchLoopCard />
        </div>
        <RecentExperimentsCard />
      </div>
    </DashboardLayout>
  )
}
