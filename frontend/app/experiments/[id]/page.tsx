import { DashboardLayout } from "@/components/dashboard-layout"
import { ExperimentDetail } from "@/components/experiments/experiment-detail"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

interface ExperimentPageProps {
  params: Promise<{ id: string }>
}

export default async function ExperimentPage({ params }: ExperimentPageProps) {
  const { id } = await params
  
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
              <BreadcrumbLink href="/experiments" className="text-sm">Experiments</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="text-sm font-medium font-mono">{id}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      }
    >
      <ExperimentDetail experimentId={id} />
    </DashboardLayout>
  )
}
