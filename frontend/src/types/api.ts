/* ─────────────────────────────────────────────────────────────
   DataSentinel — Shared TypeScript Interfaces
   Replaces pervasive `any` types across all components.
   ───────────────────────────────────────────────────────────── */

export interface UploadResponse {
  status: string;
  session_id: string;
  total_rows: number;
  anomaly_count: number;
  recommendation: string;
  recommended_cleaning: string;
  cleaning_rationale: string;
  parquet_path: string;
}

export interface AnomalyRow {
  is_anomaly: boolean;
  AI_Reason: string;
  Threat_Score: number;
  SHAP_Payload?: string;
  [key: string]: unknown;
}

export interface SessionDataResponse {
  data: AnomalyRow[];
  total_anomalies: number;
  // FE-06 FIX: total_rows is returned by the backend but was missing from this interface
  total_rows: number;
}

export interface CleanResponse {
  status: string;
  action_taken: string;
  original_rows: number;
  new_total: number;
}

export interface CompareResponse {
  is_dropped: boolean;
  original: Record<string, unknown>[];
  cleaned: Record<string, unknown>[];
  count: number;
}

export interface OIAInsight {
  observation: string;
  insight: string;
  action: string;
}

export interface InsightsResponse {
  insights: OIAInsight[];
}

export interface VizData {
  columns: string[];
  categorical_columns: string[];
  global_raw_hist: { bin: string; count: number }[];
  global_clean_hist: { bin: string; count: number }[];
  clean_sample: Record<string, unknown>[];
  correlation: { features: string[]; matrix: number[][] } | null;
  categorical_data: {
    column: string;
    top_values: { label: string; count: number }[];
  }[];
  health_score: number;
}

export interface QueryExploreResponse {
  sql: string;
  columns: string[];
  data: Record<string, unknown>[];
}

export interface QueryEditResponse {
  sql: string;
}

export interface EditConfirmResponse {
  status: string;
  rows_affected: number;
  columns: string[];
  preview_data: Record<string, unknown>[];
}

export interface QuarantineResponse {
  data: AnomalyRow[];
  count: number;
}
