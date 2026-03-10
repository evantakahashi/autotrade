"use client"

import * as React from "react"
import { Play, AlertTriangle, Search, TrendingUp, ArrowUpRight, ArrowDownRight } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { runAnalysis } from "@/lib/api"

type Action = "BUY" | "HOLD" | "SELL"

const actionConfig: Record<Action, { className: string; icon: React.ElementType }> = {
  BUY: { className: "border-success/30 bg-success/10 text-success", icon: ArrowUpRight },
  HOLD: { className: "border-muted-foreground/30 bg-muted/50 text-muted-foreground", icon: TrendingUp },
  SELL: { className: "border-destructive/30 bg-destructive/10 text-destructive", icon: ArrowDownRight },
}

const timeframeMap: Record<string, number> = {
  "1y": 365,
  "2y": 730,
  "3y": 1095,
}

function getScoreBgTint(score: number): string {
  if (score >= 70) return "text-success"
  if (score >= 40) return "text-warning"
  return "text-destructive"
}

export function PortfolioAnalysis() {
  const [tickers, setTickers] = React.useState("")
  const [timeframe, setTimeframe] = React.useState("1y")
  const [isAnalyzing, setIsAnalyzing] = React.useState(false)
  const [results, setResults] = React.useState<any>(null)
  const [error, setError] = React.useState<string | null>(null)

  const handleAnalyze = async () => {
    const tickerList = tickers.split(/[,\s]+/).filter(Boolean)
    if (tickerList.length === 0) return
    setIsAnalyzing(true)
    setError(null)
    setResults(null)
    try {
      const days = timeframeMap[timeframe] || 365
      const data = await runAnalysis(tickerList, days)
      setResults(data)
    } catch (e: any) {
      setError(e.message || "Analysis failed")
    } finally {
      setIsAnalyzing(false)
    }
  }

  const recommendations = results?.recommendations || []
  const warnings = results?.warnings || []

  return (
    <div className="flex flex-col gap-6">
      <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="border-b border-border/50 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
              <Search className="size-5" />
            </div>
            <div className="flex flex-col">
              <CardTitle className="text-base font-semibold tracking-tight">Portfolio Analysis</CardTitle>
              <CardDescription className="text-xs">
                Enter tickers to analyze using the current strategy
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <Input
              placeholder="Enter tickers: AAPL, NVDA, MSFT, AMD..."
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              className="flex-1 rounded-xl border-border/50 bg-background/50 text-sm placeholder:text-muted-foreground/60"
            />
            <Select value={timeframe} onValueChange={setTimeframe}>
              <SelectTrigger className="w-full rounded-xl border-border/50 bg-background/50 sm:w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="rounded-xl">
                <SelectItem value="1y">1 Year</SelectItem>
                <SelectItem value="2y">2 Years</SelectItem>
                <SelectItem value="3y">3 Years</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={handleAnalyze} disabled={isAnalyzing} className="gap-2 rounded-xl px-5">
              {isAnalyzing ? (
                <>
                  <Spinner className="size-4" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Play className="size-4" />
                  Analyze
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Alert className="rounded-xl border-destructive/30 bg-destructive/5">
          <AlertTriangle className="size-4 text-destructive" />
          <AlertTitle className="text-sm font-medium text-destructive">Error</AlertTitle>
          <AlertDescription className="text-xs text-muted-foreground">{error}</AlertDescription>
        </Alert>
      )}

      {recommendations.length > 0 && (
        <>
          <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
            <CardHeader className="flex flex-row items-center justify-between border-b border-border/50 pb-4">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-xl bg-chart-2/10 text-chart-2 ring-1 ring-chart-2/20">
                  <TrendingUp className="size-5" />
                </div>
                <div className="flex flex-col">
                  <CardTitle className="text-base font-semibold tracking-tight">Analysis Results</CardTitle>
                  <CardDescription className="text-xs">
                    Strategy v{results?.strategy_version || "?"} — {new Date().toLocaleDateString()}
                  </CardDescription>
                </div>
              </div>
              <Badge variant="secondary" className="rounded-lg border-0 bg-muted/80 font-mono text-xs">
                {recommendations.length} stocks
              </Badge>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/50 hover:bg-transparent">
                    <TableHead className="w-12 pl-6 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">#</TableHead>
                    <TableHead className="w-20 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Ticker</TableHead>
                    <TableHead className="w-24 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Action</TableHead>
                    <TableHead className="w-48 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Score</TableHead>
                    <TableHead className="w-24 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Confidence</TableHead>
                    <TableHead className="w-20 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Trend</TableHead>
                    <TableHead className="w-20 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Rel Str</TableHead>
                    <TableHead className="w-20 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Vol</TableHead>
                    <TableHead className="w-20 pr-6 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Liq</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recommendations.map((rec: any, idx: number) => {
                    const action = rec.action.toUpperCase() as Action
                    const config = actionConfig[action] || actionConfig.HOLD
                    const ActionIcon = config.icon
                    const signals = rec.signal_scores || {}
                    return (
                      <TableRow key={rec.ticker} className="border-border/50 transition-colors hover:bg-muted/30">
                        <TableCell className="pl-6 font-medium text-muted-foreground">{idx + 1}</TableCell>
                        <TableCell>
                          <span className="rounded-md bg-primary/10 px-2 py-1 font-mono text-xs font-bold text-primary ring-1 ring-primary/20">
                            {rec.ticker}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={`gap-1 rounded-lg border px-2 py-0.5 text-[10px] font-medium ${config.className}`}>
                            <ActionIcon className="size-3" />
                            {action}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Progress
                              value={rec.composite_score}
                              className="h-1.5 flex-1 bg-muted"
                            />
                            <span className="w-8 font-mono text-xs font-semibold tabular-nums">{Math.round(rec.composite_score)}</span>
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-xs tabular-nums">{Math.round(rec.confidence * 100)}%</TableCell>
                        <TableCell className={`font-mono text-xs tabular-nums ${getScoreBgTint(signals.trend || 0)}`}>
                          {signals.trend != null ? Math.round(signals.trend) : "—"}
                        </TableCell>
                        <TableCell className={`font-mono text-xs tabular-nums ${getScoreBgTint(signals.relative_strength || 0)}`}>
                          {signals.relative_strength != null ? Math.round(signals.relative_strength) : "—"}
                        </TableCell>
                        <TableCell className={`font-mono text-xs tabular-nums ${getScoreBgTint(signals.volatility || 0)}`}>
                          {signals.volatility != null ? Math.round(signals.volatility) : "—"}
                        </TableCell>
                        <TableCell className={`pr-6 font-mono text-xs tabular-nums ${getScoreBgTint(signals.liquidity || 0)}`}>
                          {signals.liquidity != null ? Math.round(signals.liquidity) : "—"}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {warnings.length > 0 && (
            <div className="flex flex-col gap-3">
              <h3 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Risk Warnings</h3>
              {warnings.map((warning: string, index: number) => (
                <Alert key={index} className="rounded-xl border-warning/30 bg-warning/5">
                  <AlertTriangle className="size-4 text-warning" />
                  <AlertTitle className="text-sm font-medium text-warning">Warning</AlertTitle>
                  <AlertDescription className="text-xs text-muted-foreground">{warning}</AlertDescription>
                </Alert>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
