"use client"

import * as React from "react"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { RefreshCw, Play, Square, Zap, Clock } from "lucide-react"

type LoopStatus = "running" | "paused" | "stopped"

const statusConfig: Record<LoopStatus, { label: string; icon: React.ElementType; className: string }> = {
  running: {
    label: "Running",
    icon: RefreshCw,
    className: "border-success/30 bg-success/10 text-success",
  },
  paused: {
    label: "Paused",
    icon: Clock,
    className: "border-warning/30 bg-warning/10 text-warning",
  },
  stopped: {
    label: "Stopped",
    icon: Square,
    className: "border-destructive/30 bg-destructive/10 text-destructive",
  },
}

export function ResearchLoopCard() {
  const [status, setStatus] = React.useState<LoopStatus>("running")
  const [tickers, setTickers] = React.useState("")

  const currentStatus = statusConfig[status]
  const StatusIcon = currentStatus.icon
  const rejections = 3
  const maxRejections = 10
  const rejectionProgress = (rejections / maxRejections) * 100

  return (
    <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader className="flex flex-row items-start justify-between border-b border-border/50 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-chart-2/10 text-chart-2 ring-1 ring-chart-2/20">
            <Zap className="size-5" />
          </div>
          <div className="flex flex-col">
            <CardTitle className="text-base font-semibold tracking-tight">Research Loop</CardTitle>
            <span className="text-xs text-muted-foreground">Automated strategy testing</span>
          </div>
        </div>
        <Badge variant="outline" className={`gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium ${currentStatus.className}`}>
          <StatusIcon className={`size-3 ${status === "running" ? "animate-spin" : ""}`} />
          {currentStatus.label}
        </Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-5 pt-5">
        <div className="flex flex-col gap-3 rounded-xl bg-muted/30 p-4 ring-1 ring-border/50">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Consecutive Rejections</span>
            <span className="font-mono text-sm font-semibold tabular-nums">{rejections}/{maxRejections}</span>
          </div>
          <Progress value={rejectionProgress} className="h-2 bg-muted" />
        </div>
        <div className="flex items-center justify-between rounded-xl bg-muted/30 p-4 ring-1 ring-border/50">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Paper Trading</span>
          <div className="flex items-center gap-2">
            <span className="rounded-md bg-primary/10 px-2 py-0.5 font-mono text-xs font-medium text-primary ring-1 ring-primary/20">exp-007</span>
            <span className="text-xs text-muted-foreground">day 6/10</span>
          </div>
        </div>
      </CardContent>
      <CardFooter className="flex flex-col gap-3 border-t border-border/50 bg-muted/20 pt-4 sm:flex-row">
        <Input
          placeholder="AAPL, MSFT, GOOG..."
          value={tickers}
          onChange={(e) => setTickers(e.target.value)}
          className="flex-1 rounded-xl border-border/50 bg-background/50 text-sm placeholder:text-muted-foreground/60"
        />
        <div className="flex gap-2">
          <Button
            variant="default"
            onClick={() => setStatus("running")}
            disabled={status === "running"}
            className="gap-2 rounded-xl px-4"
          >
            <Play className="size-3.5" />
            Start
          </Button>
          <Button
            variant="outline"
            onClick={() => setStatus("stopped")}
            disabled={status === "stopped"}
            className="gap-2 rounded-xl border-border/50 px-4"
          >
            <Square className="size-3.5" />
            Stop
          </Button>
        </div>
      </CardFooter>
    </Card>
  )
}
