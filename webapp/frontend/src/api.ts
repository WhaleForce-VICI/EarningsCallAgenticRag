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
