export interface DatasetOption {
  label: string;
  data_file: string;
  sector_map: string;
  description?: string;
}

export interface RunRecord {
  run_id: string;
  config: {
    data_file: string;
    sector_map: string;
    max_workers: number;
    chunk_size: number;
    timeout: number;
  };
  status: string;
  created_at: number;
  finished_at?: number;
  total_rows?: number;
  completed_rows: number;
  results_csv?: string;
  kg_path?: string;
  error?: string;
}

export interface RunResultRow {
  ticker: string;
  quarter: string;
  predicted_direction: string;
  direction_score: number | string;
  actual_return: number;
  error?: string;
}
