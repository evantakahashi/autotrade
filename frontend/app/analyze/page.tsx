import { DashboardLayout } from "@/components/dashboard-layout"
import { PortfolioAnalysis } from "@/components/analyze/portfolio-analysis"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

export default function AnalyzePage() {
  return (
    <DashboardLayout
      breadcrumb={
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink href="/" className="text-sm">Dashboard</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="text-sm font-medium">Analyze</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      }
    >
      <div className="flex flex-col gap-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Portfolio Analysis</h1>
          <p className="text-sm text-muted-foreground">Analyze tickers using your current trading strategy</p>
        </div>
        <PortfolioAnalysis />
      </div>
    </DashboardLayout>
  )
}
