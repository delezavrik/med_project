import type { ClassKey } from "./data";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8001/api/v1";

export type Granularity = "day" | "week" | "month";

export interface DashMetric {
  name: string;
  value: number | string;
  unit: string | null;
  delta_pct: number | null;
  delta_dir?: string;
  label_key?: ClassKey | null;
  kind: string;
}
export interface DashProblem {
  label_key: ClassKey;
  label: string;
  short: string;
  count: number;
  share: number;
  delta_pct: number | null;
  delta_dir: string;
  spark: number[];
}
export interface DashProduct {
  product_id: string;
  product_name: string;
  brand: string;
  total: number;
  problem_share: number;
  risk_score: number;
  top_labels: ClassKey[];
}
export interface DashWarning { code: string; message: string; }
export interface DashTrace { id: string; title: string; status: string; input: Record<string, unknown>; output: Record<string, unknown>; }

export interface DashboardData {
  meta: {
    total_reviews: number;
    granularity: string;
    buckets: string[];
    period: { date_from: string | null; date_to: string | null };
    prev_period: { date_from: string | null; date_to: string | null };
    execution_ms: number;
  };
  metrics: DashMetric[];
  positive: { label: string; short: string; count: number; share: number };
  problems: DashProblem[];
  series: { negative_share: number[]; by_label: Record<string, number[]> };
  positive_vs_problem: { positive_share: number[]; problem_share: number[] };
  top_products: DashProduct[];
  warnings: DashWarning[];
  trace_steps: DashTrace[];
}

export async function fetchDashboard(granularity: Granularity): Promise<DashboardData> {
  const res = await fetch(`${API_BASE}/dashboard`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ granularity }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return (await res.json()) as DashboardData;
}
