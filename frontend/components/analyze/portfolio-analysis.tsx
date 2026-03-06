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

type Action = "BUY" | "HOLD" | "SELL"

interface StockAnalysis {
  rank: number
  ticker: string
  action: Action
  score: number
  confidence: number
  trend: number
  relStr: number
  volatility: number
  liquidity: number
}

interface Warning {
  title: string
  description: string
}

const actionConfig: Record<Action, { className: string; icon: React.ElementType }> = {
  BUY: { className: "border-success/30 bg-success/10 text-success", icon: ArrowUpRight },
  HOLD: { className: "border-muted-foreground/30 bg-muted/50 text-muted-foreground", icon: TrendingUp },
  SELL: { className: "border-destructive/30 bg-destructive/10 text-destructive", icon: ArrowDownRight },
}

const mockResults: StockAnalysis[] = [
  { rank: 1, ticker: "NVDA", action: "BUY", score: 92, confidence: 94, trend: 88, relStr: 95, volatility: 72, liquidity: 98 },
  { rank: 2, ticker: "AAPL", action: "BUY", score: 85, confidence: 89, trend: 82, relStr: 88, volatility: 85, liquidity: 99 },
  { rank: 3, ticker: "MSFT", action: "BUY", score: 81, confidence: 85, trend: 78, relStr: 84, volatility: 88, liquidity: 99 },
  { rank: 4, ticker: "GOOGL", action: "BUY", score: 76, confidence: 80, trend: 72, relStr: 79, volatility: 82, liquidity: 97 },
  { rank: 5, ticker: "AMD", action: "HOLD", score: 69, confidence: 72, trend: 65, relStr: 71, volatility: 58, liquidity: 94 },
  { rank: 6, ticker: "TSLA", action: "HOLD", score: 55, confidence: 58, trend: 52, relStr: 54, volatility: 38, liquidity: 96 },
  { rank: 7, ticker: "META", action: "HOLD", score: 48, confidence: 52, trend: 45, relStr: 50, volatility: 65, liquidity: 95 },
  { rank: 8, ticker: "INTC", action: "SELL", score: 32, confidence: 78, trend: 28, relStr: 30, volatility: 45, liquidity: 92 },
]

const mockWarnings: Warning[] = [
  { title: "Sector Concentration", description: "62% Technology (max 40%)" },
  { title: "Borderline Score", description: "AMD at 69 (buy threshold: 70)" },
]

function getScoreColor(score: number): string {
  if (score >= 70) return "bg-success"
  if (score >= 40) return "bg-warning"
  return "bg-destructive"
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
  const [showResults, setShowResults] = React.useState(false)

  const handleAnalyze = () => {
    setIsAnalyzing(true)
    setTimeout(() => {
      setIsAnalyzing(false)
      setShowResults(true)
    }, 2000)
  }

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

      {showResults && (
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
                    Strategy v0.2 — {new Date().toLocaleDateString()}
                  </CardDescription>
                </div>
              </div>
              <Badge variant="secondary" className="rounded-lg border-0 bg-muted/80 font-mono text-xs">
                {mockResults.length} stocks
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
                  {mockResults.map((stock) => {
                    const config = actionConfig[stock.action]
                    const ActionIcon = config.icon
                    return (
                      <TableRow key={stock.ticker} className="border-border/50 transition-colors hover:bg-muted/30">
                        <TableCell className="pl-6 font-medium text-muted-foreground">{stock.rank}</TableCell>
                        <TableCell>
                          <span className="rounded-md bg-primary/10 px-2 py-1 font-mono text-xs font-bold text-primary ring-1 ring-primary/20">
                            {stock.ticker}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={`gap-1 rounded-lg border px-2 py-0.5 text-[10px] font-medium ${config.className}`}>
                            <ActionIcon className="size-3" />
                            {stock.action}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Progress 
                              value={stock.score} 
                              className="h-1.5 flex-1 bg-muted"
                            />
                            <span className="w-8 font-mono text-xs font-semibold tabular-nums">{stock.score}</span>
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-xs tabular-nums">{stock.confidence}%</TableCell>
                        <TableCell className={`font-mono text-xs tabular-nums ${getScoreBgTint(stock.trend)}`}>
                          {stock.trend}
                        </TableCell>
                        <TableCell className={`font-mono text-xs tabular-nums ${getScoreBgTint(stock.relStr)}`}>
                          {stock.relStr}
                        </TableCell>
                        <TableCell className={`font-mono text-xs tabular-nums ${getScoreBgTint(stock.volatility)}`}>
                          {stock.volatility}
                        </TableCell>
                        <TableCell className={`pr-6 font-mono text-xs tabular-nums ${getScoreBgTint(stock.liquidity)}`}>
                          {stock.liquidity}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <div className="flex flex-col gap-3">
            <h3 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Risk Warnings</h3>
            {mockWarnings.map((warning, index) => (
              <Alert key={index} className="rounded-xl border-warning/30 bg-warning/5">
                <AlertTriangle className="size-4 text-warning" />
                <AlertTitle className="text-sm font-medium text-warning">{warning.title}</AlertTitle>
                <AlertDescription className="text-xs text-muted-foreground">{warning.description}</AlertDescription>
              </Alert>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
