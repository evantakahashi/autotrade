const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Strategy
export const getCurrentStrategy = () => apiFetch<any>("/api/strategy/current");
export const getStrategyHistory = () => apiFetch<any[]>("/api/strategy/history");

// Experiments
export const getExperiments = (last = 10) => apiFetch<any[]>(`/api/experiments?last=${last}`);
export const getExperiment = (id: string) => apiFetch<any>(`/api/experiments/${id}`);
export const getPaperTrades = (id: string) => apiFetch<any[]>(`/api/experiments/${id}/paper-trades`);

// Loop
export const getLoopStatus = () => apiFetch<any>("/api/loop/status");
export const startLoop = (tickers: string[], days = 730, cooldown = 3600) =>
  apiFetch<any>("/api/loop/start", {
    method: "POST",
    body: JSON.stringify({ tickers, days, cooldown }),
  });
export const stopLoop = () => apiFetch<any>("/api/loop/stop", { method: "POST" });

// Analyze
export const runAnalysis = (tickers: string[], days = 365) =>
  apiFetch<any>("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ tickers, days }),
  });

// Scores
export const getScores = (ticker: string, last = 10) =>
  apiFetch<any[]>(`/api/scores/${ticker}?last=${last}`);
