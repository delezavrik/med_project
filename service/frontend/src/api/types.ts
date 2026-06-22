export type QuerySource = "template_ui" | "chat";
export type ToolName = "postgres" | "qdrant";
export type AnswerMode = "template" | "llm";

export type Intent =
  | "count_by_problem"
  | "top_problems"
  | "problem_dynamics"
  | "top_products_by_problem"
  | "review_examples"
  | "period_comparison"
  | "product_summary"
  | "recommendations"
  | "problem_growth_analysis";

export type GroupBy = "day" | "week" | "month" | "product" | "brand" | "category" | "label";

export interface ReviewFilters {
  date_from?: string | null;
  date_to?: string | null;
  labels?: string[];
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
}

export interface TemplateExecuteRequest {
  filters: ReviewFilters;
  group_by?: GroupBy | null;
  semantic_query?: string | null;
  add_analytical_summary: boolean;
  limit: number;
}

export interface ChatAskRequest {
  message: string;
  force_answer_mode?: AnswerMode | null;
}

export interface AnswerResponse {
  parsed_query: ParsedQuery;
  result: unknown;
  answer_mode: AnswerMode;
  answer_text: string;
  ui_blocks: Array<Record<string, unknown>>;
}
