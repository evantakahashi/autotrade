"use client"

import * as React from "react"
import Link from "next/link"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import { FlaskConical, ArrowUpRight, ArrowDownRight, ChevronRight, Check, X, Clock, AlertTriangle } from "lucide-react"
import { getExperiments } from "@/lib/api"

type Decision = "promoted" | "rejected" | "paper_testing" | "invalidated"

const decisionConfig: Record<Decision, { icon: React.ElementType; label: string; className: string }> = {
  promoted: {
    icon: Check,
    label: "Promoted",
    className: "border-success/30 bg-success/10 text-success",
  },
  rejected: {
    icon: X,
    label: "Rejected",
    className: "border-destructive/30 bg-destructive/10 text-destructive",
  },
  paper_testing: {
    icon: Clock,
    label: "Testing",
    className: "border-warning/30 bg-warning/10 text-warning",
  },
  invalidated: {
    icon: AlertTriangle,
    label: "Invalid",
    className: "border-muted-foreground/30 bg-muted/50 text-muted-foreground",
  },
}

interface Experiment {
  experiment_id: string
  parent_version: string | null
  config_diff: any
  decision: Decision | null
  metrics: any
  created_at: string
}

export function RecentExperimentsCard() {
  const [experiments, setExperiments] = React.useState<Experiment[]>([])
  const [loading, setLoading] = React.useState(true)
  const [currentPage, setCurrentPage] = React.useState(1)
  const itemsPerPage = 5

  React.useEffect(() => {
    getExperiments(50)
      .then(setExperiments)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="flex flex-row items-center justify-between border-b border-border/50 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-chart-3/10 text-chart-3 ring-1 ring-chart-3/20">
              <FlaskConical className="size-5" />
            </div>
            <div className="flex flex-col gap-1">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          {[1,2,3,4,5].map(i => <Skeleton key={i} className="mb-2 h-10 w-full" />)}
        </CardContent>
      </Card>
    )
  }

  const totalPages = Math.max(1, Math.ceil(experiments.length / itemsPerPage))
  const paginatedExperiments = experiments.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  )

  return (
    <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader className="flex flex-row items-center justify-between border-b border-border/50 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-chart-3/10 text-chart-3 ring-1 ring-chart-3/20">
            <FlaskConical className="size-5" />
          </div>
          <div className="flex flex-col">
            <CardTitle className="text-base font-semibold tracking-tight">Recent Experiments</CardTitle>
            <span className="text-xs text-muted-foreground">{experiments.length} total experiments</span>
          </div>
        </div>
        <Link href="/experiments" className="flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground">
          View all
          <ChevronRight className="size-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="border-border/50 hover:bg-transparent">
              <TableHead className="w-24 pl-6 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">ID</TableHead>
              <TableHead className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Config Diff</TableHead>
              <TableHead className="w-28 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Status</TableHead>
              <TableHead className="w-24 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Sharpe</TableHead>
              <TableHead className="w-28 pr-6 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedExperiments.map((exp) => {
              const decision = (exp.decision as Decision) || "invalidated"
              const config = decisionConfig[decision] || decisionConfig.invalidated
              const DecisionIcon = config.icon
              const sharpe = exp.metrics?.sharpe
              const isPositive = sharpe != null && sharpe > 0
              return (
                <TableRow key={exp.experiment_id} className="group cursor-pointer border-border/50 transition-colors hover:bg-muted/30">
                  <TableCell className="pl-6">
                    <Link
                      href={`/experiments/${exp.experiment_id}`}
                      className="rounded-md bg-primary/10 px-2 py-1 font-mono text-xs font-medium text-primary ring-1 ring-primary/20 transition-all group-hover:bg-primary/20"
                    >
                      {exp.experiment_id}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-xs">
                    <span className="line-clamp-1 text-sm font-mono">{JSON.stringify(exp.config_diff)}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`gap-1 rounded-lg border px-2 py-0.5 text-[10px] font-medium ${config.className}`}>
                      <DecisionIcon className="size-3" />
                      {config.label}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {sharpe != null ? (
                      <span className={`inline-flex items-center gap-0.5 font-mono text-sm font-medium tabular-nums ${isPositive ? "text-success" : "text-destructive"}`}>
                        {isPositive ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
                        {Number(sharpe).toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="pr-6 text-right font-mono text-xs text-muted-foreground">
                    {exp.created_at?.split("T")[0] || "—"}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
        {totalPages > 1 && (
          <div className="border-t border-border/50 px-6 py-4">
            <Pagination>
              <PaginationContent className="gap-1">
                <PaginationItem>
                  <PaginationPrevious
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      setCurrentPage(Math.max(1, currentPage - 1))
                    }}
                    className={`rounded-lg border border-border/50 bg-transparent px-3 text-xs transition-colors hover:bg-muted ${currentPage === 1 ? "pointer-events-none opacity-50" : ""}`}
                  />
                </PaginationItem>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                  <PaginationItem key={page}>
                    <PaginationLink
                      href="#"
                      onClick={(e) => {
                        e.preventDefault()
                        setCurrentPage(page)
                      }}
                      isActive={currentPage === page}
                      className={`size-9 rounded-lg border text-xs transition-colors ${currentPage === page ? "border-primary/50 bg-primary/10 text-primary" : "border-border/50 bg-transparent hover:bg-muted"}`}
                    >
                      {page}
                    </PaginationLink>
                  </PaginationItem>
                ))}
                <PaginationItem>
                  <PaginationNext
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      setCurrentPage(Math.min(totalPages, currentPage + 1))
                    }}
                    className={`rounded-lg border border-border/50 bg-transparent px-3 text-xs transition-colors hover:bg-muted ${currentPage === totalPages ? "pointer-events-none opacity-50" : ""}`}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
