"use client"

import * as React from "react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { TrendingUp, ArrowUpRight } from "lucide-react"
import { getCurrentStrategy } from "@/lib/api"

export function CurrentStrategyCard() {
  const [strategy, setStrategy] = React.useState<any>(null)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    getCurrentStrategy()
      .then(setStrategy)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="flex flex-row items-start justify-between border-b border-border/50 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
              <TrendingUp className="size-5" />
            </div>
            <div className="flex flex-col gap-1">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-5">
          <div className="grid grid-cols-2 gap-5">
            {[1,2,3,4].map(i => (
              <div key={i} className="group flex flex-col gap-2 rounded-xl bg-muted/30 p-4 ring-1 ring-border/50">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-7 w-16" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  const metrics = strategy?.metrics || {}
  const stats = [
    { label: "Sharpe Ratio", value: metrics.sharpe != null ? String(metrics.sharpe) : "—" },
    { label: "CAGR", value: metrics.cagr != null ? `${(metrics.cagr * 100).toFixed(1)}%` : "—" },
    { label: "Max Drawdown", value: metrics.max_drawdown != null ? `${(metrics.max_drawdown * 100).toFixed(1)}%` : "—" },
    { label: "Win Rate", value: metrics.win_rate != null ? `${(metrics.win_rate * 100).toFixed(0)}%` : "—" },
  ]

  return (
    <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader className="flex flex-row items-start justify-between border-b border-border/50 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
            <TrendingUp className="size-5" />
          </div>
          <div className="flex flex-col">
            <CardTitle className="text-base font-semibold tracking-tight">Current Strategy</CardTitle>
            <span className="text-xs text-muted-foreground">
              {strategy?.promoted_date ? `Promoted ${strategy.promoted_date.split("T")[0]}` : "No promotion date"}
            </span>
          </div>
        </div>
        <Badge variant="secondary" className="rounded-lg border-0 bg-muted/80 font-mono text-xs">
          v{strategy?.version || "—"}
        </Badge>
      </CardHeader>
      <CardContent className="pt-5">
        <div className="grid grid-cols-2 gap-5">
          {stats.map((stat) => (
            <div key={stat.label} className="group flex flex-col gap-2 rounded-xl bg-muted/30 p-4 ring-1 ring-border/50 transition-colors hover:bg-muted/50">
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {stat.label}
              </span>
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-2xl font-bold tabular-nums tracking-tight">
                  {stat.value}
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
