"use client"

import * as React from "react"
import Link from "next/link"
import { Check, X, GitBranch, Calendar, FlaskConical, Settings, BarChart3, Shield, LineChart as LineChartIcon, MessageSquare, ArrowRight } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
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
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import { getExperiment, getPaperTrades } from "@/lib/api"

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
    icon: FlaskConical,
    label: "Testing",
    className: "border-warning/30 bg-warning/10 text-warning",
  },
  invalidated: {
    icon: X,
    label: "Invalid",
    className: "border-muted-foreground/30 bg-muted/50 text-muted-foreground",
  },
}

interface ExperimentDetailProps {
  experimentId: string
}

export function ExperimentDetail({ experimentId }: ExperimentDetailProps) {
  const [experiment, setExperiment] = React.useState<any>(null)
  const [paperTrades, setPaperTrades] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    Promise.all([
      getExperiment(experimentId),
      getPaperTrades(experimentId),
    ]).then(([exp, trades]) => {
      setExperiment(exp)
      setPaperTrades(trades)
    }).catch((e) => {
      setError(e.message || "Failed to load experiment")
    }).finally(() => setLoading(false))
  }, [experimentId])

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
          <CardContent className="p-6">
            <div className="flex flex-col gap-4">
              <Skeleton className="h-12 w-64" />
              <Skeleton className="h-4 w-96" />
            </div>
          </CardContent>
        </Card>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      </div>
    )
  }

  if (error || !experiment) {
    return (
      <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
        <CardContent className="p-6">
          <p className="text-sm text-destructive">{error || "Experiment not found"}</p>
        </CardContent>
      </Card>
    )
  }

  const decision: Decision = (experiment.decision as Decision) || "invalidated"
  const config = decisionConfig[decision] || decisionConfig.invalidated
  const DecisionIcon = config.icon
  const metrics = experiment.metrics || {}
  const configDiff = experiment.config_diff || {}

  // Build config changes from config_diff
  const configChanges: { key: string; value: string }[] = []
  function flattenDiff(obj: any, prefix = "") {
    for (const [k, v] of Object.entries(obj)) {
      const path = prefix ? `${prefix}.${k}` : k
      if (v && typeof v === "object" && !Array.isArray(v)) {
        flattenDiff(v, path)
      } else {
        configChanges.push({ key: path, value: String(v) })
      }
    }
  }
  flattenDiff(configDiff)

  // Build chart data from paper trades
  const chartData = paperTrades.map((t, i) => ({
    day: i + 1,
    baseline: Number((t.baseline_cumulative * 100).toFixed(2)),
    experiment: Number((t.experiment_cumulative * 100).toFixed(2)),
  }))

  // Build metrics table
  const metricsEntries = Object.entries(metrics).map(([key, val]) => ({
    metric: key,
    value: val,
  }))

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
        <CardContent className="p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
                  <FlaskConical className="size-6" />
                </div>
                <div>
                  <h1 className="flex items-center gap-3 text-xl font-bold tracking-tight">
                    <span className="rounded-lg bg-muted px-3 py-1 font-mono">{experiment.experiment_id}</span>
                    <Badge variant="outline" className={`gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium ${config.className}`}>
                      <DecisionIcon className="size-3" />
                      {config.label}
                    </Badge>
                  </h1>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-1.5 rounded-lg bg-muted/50 px-3 py-1.5 ring-1 ring-border/50">
                <GitBranch className="size-3.5" />
                <span>Parent:</span>
                <span className="font-mono font-medium text-foreground">{experiment.parent_version || "—"}</span>
              </div>
              <div className="flex items-center gap-1.5 rounded-lg bg-muted/50 px-3 py-1.5 ring-1 ring-border/50">
                <Calendar className="size-3.5" />
                <span>Created:</span>
                <span className="font-medium text-foreground">{experiment.created_at?.split("T")[0] || "—"}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Config and Metrics */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
          <CardHeader className="flex flex-row items-center gap-3 border-b border-border/50 pb-4">
            <div className="flex size-9 items-center justify-center rounded-lg bg-chart-3/10 text-chart-3 ring-1 ring-chart-3/20">
              <Settings className="size-4" />
            </div>
            <CardTitle className="text-sm font-semibold tracking-tight">Config Changes</CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <div className="rounded-xl bg-muted/30 p-4 ring-1 ring-border/50">
              <div className="flex flex-col gap-2 font-mono text-sm">
                {configChanges.length > 0 ? configChanges.map((change, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2 py-1">
                    <span className="text-muted-foreground">{change.key}:</span>
                    <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-success">
                      {change.value}
                    </span>
                  </div>
                )) : (
                  <span className="text-xs text-muted-foreground">No config changes</span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
          <CardHeader className="flex flex-row items-center gap-3 border-b border-border/50 pb-4">
            <div className="flex size-9 items-center justify-center rounded-lg bg-chart-2/10 text-chart-2 ring-1 ring-chart-2/20">
              <BarChart3 className="size-4" />
            </div>
            <CardTitle className="text-sm font-semibold tracking-tight">Metrics</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {metricsEntries.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow className="border-border/50 hover:bg-transparent">
                    <TableHead className="pl-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Metric</TableHead>
                    <TableHead className="pr-4 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Value</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {metricsEntries.map((m) => (
                    <TableRow key={m.metric} className="border-border/50 transition-colors hover:bg-muted/30">
                      <TableCell className="pl-4 text-sm capitalize">{m.metric.replace(/_/g, " ")}</TableCell>
                      <TableCell className="pr-4 text-right font-mono text-xs font-medium tabular-nums">
                        {typeof m.value === "number" ? Number(m.value).toFixed(2) : String(m.value)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-4">
                <span className="text-xs text-muted-foreground">No metrics available</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Paper Trading */}
      {chartData.length > 0 && (
        <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
          <CardHeader className="flex flex-row items-center gap-3 border-b border-border/50 pb-4">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
              <LineChartIcon className="size-4" />
            </div>
            <div className="flex flex-col">
              <CardTitle className="text-sm font-semibold tracking-tight">Paper Trading</CardTitle>
              <CardDescription className="text-xs">Live comparison vs baseline strategy</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-5 p-4">
            <div className="h-64 rounded-xl bg-muted/20 p-4 ring-1 ring-border/50">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" />
                  <XAxis
                    dataKey="day"
                    tickFormatter={(v) => `D${v}`}
                    className="text-[10px]"
                    stroke="hsl(var(--muted-foreground))"
                    strokeWidth={0}
                    tick={{ fill: "hsl(var(--muted-foreground))" }}
                  />
                  <YAxis
                    tickFormatter={(v) => `${v}%`}
                    className="text-[10px]"
                    stroke="hsl(var(--muted-foreground))"
                    strokeWidth={0}
                    tick={{ fill: "hsl(var(--muted-foreground))" }}
                  />
                  <Tooltip
                    formatter={(value: number) => [`${value.toFixed(1)}%`, ""]}
                    labelFormatter={(label) => `Day ${label}`}
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "12px",
                      fontSize: "12px",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px" }} />
                  <Line
                    type="monotone"
                    dataKey="baseline"
                    name="Baseline"
                    stroke="hsl(var(--muted-foreground))"
                    strokeDasharray="5 5"
                    dot={false}
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="experiment"
                    name="Experiment"
                    stroke="hsl(var(--primary))"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2 rounded-lg bg-muted/30 px-3 py-2 ring-1 ring-border/50">
                <span className="text-[11px] uppercase tracking-wider text-muted-foreground">Days:</span>
                <span className="font-mono text-xs font-semibold">{paperTrades.length}</span>
              </div>
              {chartData.length > 0 && (
                <div className="flex items-center gap-2 rounded-lg bg-muted/30 px-3 py-2 ring-1 ring-border/50">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground">Beat Baseline:</span>
                  <span className={`font-mono text-xs font-semibold ${chartData[chartData.length - 1].experiment > chartData[chartData.length - 1].baseline ? "text-success" : "text-destructive"}`}>
                    {chartData[chartData.length - 1].experiment > chartData[chartData.length - 1].baseline ? "Yes" : "No"}
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Decision */}
      <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="flex flex-row items-center gap-3 border-b border-border/50 pb-4">
          <div className="flex size-9 items-center justify-center rounded-lg bg-chart-5/10 text-chart-5 ring-1 ring-chart-5/20">
            <MessageSquare className="size-4" />
          </div>
          <CardTitle className="text-sm font-semibold tracking-tight">Decision</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 p-4">
          <Badge variant="outline" className={`w-fit gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${config.className}`}>
            <DecisionIcon className="size-3.5" />
            {config.label}
          </Badge>
        </CardContent>
      </Card>
    </div>
  )
}
