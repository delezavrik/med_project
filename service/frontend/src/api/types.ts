export type QuerySource = "template_ui" | "chat";
export type ToolName = "postgres" | "qdrant";
export type AnswerMode = "template" | "llm";

export type Intent =
  | "count_by_problem"
  | "top_problems"
  | "problem_dynamics"
  | "review_samples"
  | "period_comparison"
  | "problem_share"
  | "problem_growth"
  | "label_cooccurrence"
  | "keyword_search"
  | "positive_vs_problem"
  | "top_products_by_problem"
  | "review_examples"
  | "product_summary"
  | "recommendations"
  | "problem_growth_analysis";

export type GroupBy = "day" | "week" | "month" | "product" | "brand" | "category" | "label";

export interface ReviewFilters {
  date_from?: string | null;
  date_to?: string | null;
  labels?: string[];
  keyword?: string | null;
  category?: string | null;
  brand?: string | null;
  product_id?: string | null;
  product_name?: string | null;
  min_rating?: number | null;
  max_rating?: number | null;
}

export interface ParsedQuery {
  source: QuerySource;
  intent: Intent;
  filters: ReviewFilters;
  group_by?: GroupBy | null;
  semantic_query?: string | null;
  tools: ToolName[];
  answer_mode: AnswerMode;
  limit: number;
  examples_limit: number;
}

export interface TemplateExecuteRequest {
  filters: ReviewFilters;
  group_by?: GroupBy | null;
  semantic_query?: string | null;
  add_analytical_summary: boolean;
  limit: number;
  examples_limit: number;
}

export interface ChatAskRequest {
  message: string;
  force_answer_mode?: AnswerMode | null;
}

export interface AnswerResponse {
  parsed_query: ParsedQuery;
  result: StructuredResult;
  answer_mode: AnswerMode;
  answer_text: string;
  ui_blocks: UiBlock[];
  execution_ms?: number | null;
  trace_steps: TraceStep[];
}

export interface TraceStep {
  id: string;
  title: string;
  status: string;
  duration_ms?: number | null;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

export interface MetricBlock {
  name: string;
  value: number | string | null;
  unit?: string | null;
}

export interface ResultRow {
  data: Record<string, unknown>;
}

export interface ReviewExample {
  review_id?: string | null;
  text: string;
  labels: string[];
  product_id?: string | null;
  product_name?: string | null;
  category?: string | null;
  brand?: string | null;
  rating?: number | null;
  date?: string | null;
  score?: number | null;
}

export interface StructuredResult {
  parsed_query: ParsedQuery;
  metrics: MetricBlock[];
  rows: ResultRow[];
  examples: ReviewExample[];
  warnings: string[];
  raw: Record<string, unknown>;
}

export type UiBlock =
  | { type: "metrics"; items: MetricBlock[] }
  | { type: "table"; rows: Array<Record<string, unknown>> }
  | { type: "reviews"; items: ReviewExample[] }
  | { type: "warnings"; items: string[] };

export interface TemplateInfo {
  id: string;
  title: string;
  description: string;
  default_answer_mode: AnswerMode;
  allow_llm_summary: boolean;
  needs_semantic_query: boolean;
  label_mode: "required" | "subset" | "optional" | "hidden";
  keyword_mode: "required" | "optional" | "hidden";
  default_group_by?: GroupBy | null;
}

export interface ProductFacet {
  product_id?: string | null;
  product_name?: string | null;
}

export interface FacetsResponse {
  labels: string[];
  problem_labels: string[];
  positive_label: string;
  categories: string[];
  brands: string[];
  products: ProductFacet[];
  date_min?: string | null;
  date_max?: string | null;
  warnings: string[];
}
