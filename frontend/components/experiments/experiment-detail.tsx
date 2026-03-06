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
import { Progress } from "@/components/ui/progress"
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

type Decision = "promoted" | "rejected" | "paper_testing" | "invalidated"

interface ExperimentData {
  id: string
  hypothesis: string
  decision: Decision
  parent: string
  created: string
  configChanges: { key: string; old: string; new: string }[]
  metrics: { metric: string; baseline: number; experiment: number; unit: string }[]
  gates: { name: string; passed: boolean; detail: string }[]
  paperTradingData: { day: number; baseline: number; experiment: number }[]
  paperTradingStats: { days: string; beatBaseline: string; directionalConsistency: string }
  reasoning: string
  promotedDate?: string
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

const mockExperiment: ExperimentData = {
  id: "exp-007",
  hypothesis: "Tighten sell threshold from 50 to 45 to capture more profit during reversals",
  decision: "paper_testing",
  parent: "v0.1",
  created: "2026-03-06",
  configChanges: [
    { key: "weights.trend", old: "0.35", new: "0.40" },
    { key: "weights.fundamentals", old: "0.20", new: "0.15" },
    { key: "thresholds.sell", old: "50", new: "45" },
    { key: "thresholds.confidence_min", old: "0.65", new: "0.70" },
  ],
  metrics: [
    { metric: "Sharpe", baseline: 1.19, experiment: 1.24, unit: "" },
    { metric: "CAGR", baseline: 16.8, experiment: 18.3, unit: "%" },
    { metric: "Max Drawdown", baseline: 14.2, experiment: 12.1, unit: "%" },
    { metric: "Hit Rate", baseline: 58, experiment: 62, unit: "%" },
    { metric: "Monthly Turnover", baseline: 22, experiment: 28, unit: "%" },
  ],
  gates: [
    { name: "Sharpe", passed: true, detail: "1.24 > 1.15 baseline (+0.05)" },
    { name: "Walk-Forward", passed: true, detail: "Won 4/4 windows (100%)" },
    { name: "Drawdown", passed: true, detail: "12.1% < 15% max allowed" },
    { name: "Turnover", passed: false, detail: "28% > 25% max allowed" },
    { name: "Regime Diversity", passed: true, detail: "Profitable in 3/4 regimes" },
    { name: "Paper Trading", passed: true, detail: "Day 6/10 — tracking +2.1%" },
  ],
  paperTradingData: [
    { day: 1, baseline: 0, experiment: 0 },
    { day: 2, baseline: 0.3, experiment: 0.5 },
    { day: 3, baseline: 0.8, experiment: 1.2 },
    { day: 4, baseline: 0.5, experiment: 1.4 },
    { day: 5, baseline: 1.0, experiment: 1.8 },
    { day: 6, baseline: 1.2, experiment: 2.1 },
  ],
  paperTradingStats: {
    days: "6/10",
    beatBaseline: "Yes",
    directionalConsistency: "70%",
  },
  reasoning: "This experiment tightens the sell threshold to 45 from 50, aiming to lock in profits earlier during price reversals. Initial backtesting shows improved Sharpe ratio and reduced drawdown, though monthly turnover has increased slightly above the 25% guideline. Paper trading results through day 6 show consistent outperformance vs baseline, with strong directional consistency. The turnover gate failure is marginal and may be acceptable given the improvements in risk-adjusted returns.",
  promotedDate: undefined,
}

function getMetricDelta(baseline: number, experiment: number, metric: string): { value: string; isPositive: boolean } {
  const delta = experiment - baseline
  const isDrawdown = metric.toLowerCase().includes("drawdown") || metric.toLowerCase().includes("turnover")
  const isPositive = isDrawdown ? delta < 0 : delta > 0
  const sign = delta > 0 ? "+" : ""
  return {
    value: `${sign}${delta.toFixed(1)}`,
    isPositive,
  }
}

interface ExperimentDetailProps {
  experimentId: string
}

export function ExperimentDetail({ experimentId }: ExperimentDetailProps) {
  const experiment = { ...mockExperiment, id: experimentId }
  const config = decisionConfig[experiment.decision]
  const DecisionIcon = config.icon
  const isPaperTesting = experiment.decision === "paper_testing"
  const paperProgress = (parseInt(experiment.paperTradingStats.days.split("/")[0]) / parseInt(experiment.paperTradingStats.days.split("/")[1])) * 100

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
                    <span className="rounded-lg bg-muted px-3 py-1 font-mono">{experiment.id}</span>
                    <Badge variant="outline" className={`gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium ${config.className}`}>
                      <DecisionIcon className="size-3" />
                      {config.label}
                    </Badge>
                  </h1>
                </div>
              </div>
              <p className="max-w-2xl text-sm italic text-muted-foreground leading-relaxed">{experiment.hypothesis}</p>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-1.5 rounded-lg bg-muted/50 px-3 py-1.5 ring-1 ring-border/50">
                <GitBranch className="size-3.5" />
                <span>Parent:</span>
                <span className="font-mono font-medium text-foreground">{experiment.parent}</span>
              </div>
              <div className="flex items-center gap-1.5 rounded-lg bg-muted/50 px-3 py-1.5 ring-1 ring-border/50">
                <Calendar className="size-3.5" />
                <span>Created:</span>
                <span className="font-medium text-foreground">{experiment.created}</span>
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
                {experiment.configChanges.map((change, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2 py-1">
                    <span className="text-muted-foreground">{change.key}:</span>
                    <span className="rounded-md bg-destructive/10 px-1.5 py-0.5 text-destructive line-through">
                      {change.old}
                    </span>
                    <ArrowRight className="size-3 text-muted-foreground" />
                    <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-success">
                      {change.new}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
          <CardHeader className="flex flex-row items-center gap-3 border-b border-border/50 pb-4">
            <div className="flex size-9 items-center justify-center rounded-lg bg-chart-2/10 text-chart-2 ring-1 ring-chart-2/20">
              <BarChart3 className="size-4" />
            </div>
            <CardTitle className="text-sm font-semibold tracking-tight">Metrics Comparison</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="border-border/50 hover:bg-transparent">
                  <TableHead className="pl-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Metric</TableHead>
                  <TableHead className="text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Base</TableHead>
                  <TableHead className="text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Exp</TableHead>
                  <TableHead className="pr-4 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Delta</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {experiment.metrics.map((m) => {
                  const delta = getMetricDelta(m.baseline, m.experiment, m.metric)
                  return (
                    <TableRow key={m.metric} className="border-border/50 transition-colors hover:bg-muted/30">
                      <TableCell className="pl-4 text-sm">{m.metric}</TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums text-muted-foreground">
                        {m.baseline}{m.unit}
                      </TableCell>
                      <TableCell className={`text-right font-mono text-xs font-medium tabular-nums ${delta.isPositive ? "text-success" : "text-destructive"}`}>
                        {m.experiment}{m.unit}
                      </TableCell>
                      <TableCell className={`pr-4 text-right font-mono text-xs tabular-nums ${delta.isPositive ? "text-success" : "text-destructive"}`}>
                        {delta.value}{m.unit}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* Validation Gates */}
      <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="flex flex-row items-center gap-3 border-b border-border/50 pb-4">
          <div className="flex size-9 items-center justify-center rounded-lg bg-chart-4/10 text-chart-4 ring-1 ring-chart-4/20">
            <Shield className="size-4" />
          </div>
          <div className="flex flex-col">
            <CardTitle className="text-sm font-semibold tracking-tight">Validation Gates</CardTitle>
            <CardDescription className="text-xs">{experiment.gates.filter(g => g.passed).length}/{experiment.gates.length} gates passed</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {experiment.gates.map((gate) => (
              <div
                key={gate.name}
                className={`flex flex-col gap-2 rounded-xl p-4 ring-1 transition-colors ${
                  gate.passed ? "bg-success/5 ring-success/20" : "bg-destructive/5 ring-destructive/20"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{gate.name}</span>
                  {gate.passed ? (
                    <div className="flex size-6 items-center justify-center rounded-full bg-success/20 text-success ring-1 ring-success/30">
                      <Check className="size-3.5" />
                    </div>
                  ) : (
                    <div className="flex size-6 items-center justify-center rounded-full bg-destructive/20 text-destructive ring-1 ring-destructive/30">
                      <X className="size-3.5" />
                    </div>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">{gate.detail}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Paper Trading */}
      {(isPaperTesting || experiment.paperTradingData.length > 0) && (
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
                <LineChart data={experiment.paperTradingData}>
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
              {[
                { label: "Days", value: experiment.paperTradingStats.days },
                { label: "Beat Baseline", value: experiment.paperTradingStats.beatBaseline, isPositive: experiment.paperTradingStats.beatBaseline === "Yes" },
                { label: "Consistency", value: experiment.paperTradingStats.directionalConsistency },
              ].map((stat) => (
                <div key={stat.label} className="flex items-center gap-2 rounded-lg bg-muted/30 px-3 py-2 ring-1 ring-border/50">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground">{stat.label}:</span>
                  <span className={`font-mono text-xs font-semibold ${stat.isPositive !== undefined ? (stat.isPositive ? "text-success" : "text-destructive") : ""}`}>
                    {stat.value}
                  </span>
                </div>
              ))}
            </div>
            {isPaperTesting && (
              <Progress value={paperProgress} className="h-1.5 bg-muted" />
            )}
          </CardContent>
        </Card>
      )}

      {/* Decision */}
      <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="flex flex-row items-center gap-3 border-b border-border/50 pb-4">
          <div className="flex size-9 items-center justify-center rounded-lg bg-chart-5/10 text-chart-5 ring-1 ring-chart-5/20">
            <MessageSquare className="size-4" />
          </div>
          <CardTitle className="text-sm font-semibold tracking-tight">Decision Reasoning</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 p-4">
          <Badge variant="outline" className={`w-fit gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${config.className}`}>
            <DecisionIcon className="size-3.5" />
            {config.label}
          </Badge>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {experiment.reasoning}
          </p>
          {experiment.promotedDate && (
            <p className="text-xs text-muted-foreground">
              Promoted to <Link href="/" className="font-mono text-primary hover:underline">v0.2</Link> on {experiment.promotedDate}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
