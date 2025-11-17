import type { DatasetOption, RunRecord, RunResultRow } from './types';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const payload = await resp.text();
    throw new Error(payload || resp.statusText);
  }
  return (await resp.json()) as T;
}

export async function fetchOptions(): Promise<{ datasets: DatasetOption[] }> {
  const resp = await fetch('/api/options');
  return handle(resp);
}

export async function fetchRuns(): Promise<{ runs: RunRecord[] }> {
  const resp = await fetch('/api/runs');
  return handle(resp);
}

export async function fetchRun(runId: string): Promise<{ run: RunRecord }> {
  const resp = await fetch(`/api/runs/${runId}`);
  return handle(resp);
}

export async function createRun(payload: {
  data_file: string;
  sector_map: string;
  max_workers: number;
  chunk_size: number;
  timeout: number;
  fact_limit?: number;
  current_fact_limit?: number;
  top_k?: number;
  max_rows?: number;
}): Promise<{ run_id: string }> {
  const resp = await fetch('/api/run', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
  return handle(resp);
}

export async function fetchResults(runId: string): Promise<RunResultRow[]> {
  const resp = await fetch(`/api/runs/${runId}/results`);
  return handle(resp);
}

export async function fetchLog(runId: string): Promise<{ log: string }> {
  const resp = await fetch(`/api/runs/${runId}/log`);
  return handle(resp);
}

export async function estimateRun(data_file: string, max_rows?: number, top_k?: number, fact_limit?: number, current_fact_limit?: number): Promise<any> {
  const qs = new URLSearchParams({ data_file });
  if (max_rows) qs.append("max_rows", String(max_rows));
  if (top_k) qs.append("top_k", String(top_k));
  if (fact_limit) qs.append("fact_limit", String(fact_limit));
  if (current_fact_limit) qs.append("current_fact_limit", String(current_fact_limit));
  const resp = await fetch(`/api/estimate?${qs.toString()}`);
  return handle(resp);
}

export async function clearHistory(): Promise<any> {
  const resp = await fetch(`/api/history`, { method: "DELETE" });
  return handle(resp);
}
