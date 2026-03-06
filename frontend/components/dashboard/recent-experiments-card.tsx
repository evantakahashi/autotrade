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

type Decision = "promoted" | "rejected" | "paper_testing" | "invalidated"

interface Experiment {
  id: string
  hypothesis: string
  decision: Decision
  sharpeDelta: number
  date: string
}

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

const experiments: Experiment[] = [
  { id: "exp-010", hypothesis: "Increase trend weight to 0.40", decision: "promoted", sharpeDelta: 0.15, date: "2026-03-09" },
  { id: "exp-009", hypothesis: "Add momentum crossover signal", decision: "rejected", sharpeDelta: -0.08, date: "2026-03-08" },
  { id: "exp-008", hypothesis: "Reduce position size during high VIX", decision: "promoted", sharpeDelta: 0.12, date: "2026-03-07" },
  { id: "exp-007", hypothesis: "Tighten sell threshold to 45", decision: "paper_testing", sharpeDelta: 0.05, date: "2026-03-06" },
  { id: "exp-006", hypothesis: "Include sector rotation factor", decision: "rejected", sharpeDelta: -0.22, date: "2026-03-05" },
  { id: "exp-005", hypothesis: "Adjust rebalance frequency to weekly", decision: "invalidated", sharpeDelta: 0.02, date: "2026-03-04" },
  { id: "exp-004", hypothesis: "Add earnings surprise alpha", decision: "promoted", sharpeDelta: 0.18, date: "2026-03-03" },
  { id: "exp-003", hypothesis: "Increase max position from 8% to 10%", decision: "rejected", sharpeDelta: -0.14, date: "2026-03-02" },
  { id: "exp-002", hypothesis: "Lower volatility target to 12%", decision: "promoted", sharpeDelta: 0.09, date: "2026-03-01" },
  { id: "exp-001", hypothesis: "Use VWAP instead of close price", decision: "invalidated", sharpeDelta: -0.03, date: "2026-02-28" },
]

export function RecentExperimentsCard() {
  const [currentPage, setCurrentPage] = React.useState(1)
  const itemsPerPage = 5
  const totalPages = Math.ceil(experiments.length / itemsPerPage)
  
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
              <TableHead className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Hypothesis</TableHead>
              <TableHead className="w-28 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Status</TableHead>
              <TableHead className="w-24 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Delta</TableHead>
              <TableHead className="w-28 pr-6 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedExperiments.map((exp) => {
              const config = decisionConfig[exp.decision]
              const DecisionIcon = config.icon
              const isPositive = exp.sharpeDelta > 0
              return (
                <TableRow key={exp.id} className="group cursor-pointer border-border/50 transition-colors hover:bg-muted/30">
                  <TableCell className="pl-6">
                    <Link 
                      href={`/experiments/${exp.id}`}
                      className="rounded-md bg-primary/10 px-2 py-1 font-mono text-xs font-medium text-primary ring-1 ring-primary/20 transition-all group-hover:bg-primary/20"
                    >
                      {exp.id}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-xs">
                    <span className="line-clamp-1 text-sm">{exp.hypothesis}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`gap-1 rounded-lg border px-2 py-0.5 text-[10px] font-medium ${config.className}`}>
                      <DecisionIcon className="size-3" />
                      {config.label}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <span className={`inline-flex items-center gap-0.5 font-mono text-sm font-medium tabular-nums ${isPositive ? "text-success" : "text-destructive"}`}>
                      {isPositive ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
                      {isPositive ? "+" : ""}{exp.sharpeDelta.toFixed(2)}
                    </span>
                  </TableCell>
                  <TableCell className="pr-6 text-right font-mono text-xs text-muted-foreground">
                    {exp.date}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
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
      </CardContent>
    </Card>
  )
}
