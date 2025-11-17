from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import REPO_ROOT
from .run_manager import RUN_MANAGER, RunRecord


app = FastAPI(title="Earnings Call Agentic RAG API", version="0.2.0")

FRONTEND_DIST = REPO_ROOT / "webapp" / "frontend" / "dist"


DATASET_OPTIONS = [
  {
    "label": "Sample 2 rows (demo)",
    "data_file": "sample_data.csv",
    "sector_map": "gics_sector_map_nyse.csv",
    "description": "兩筆資料，適合快速測試",
  },
  {
    "label": "NYSE full dataset",
    "data_file": "merged_data_nyse.csv",
    "sector_map": "gics_sector_map_nyse.csv",
    "description": "完整 NYSE >5% shock",
  },
  {
    "label": "NASDAQ full dataset",
    "data_file": "merged_data_nasdaq.csv",
    "sector_map": "gics_sector_map_nasdaq.csv",
    "description": "完整 NASDAQ >5% shock",
  },
  {
    "label": "MAEC benchmark",
    "data_file": "maec_transcripts.csv",
    "sector_map": "gics_sector_map_maec.csv",
    "description": "MAEC earnings call benchmark",
  },
]


def serialize_runs(records: list[RunRecord]) -> list[dict]:
  return [r.to_dict() for r in records]


class RunPayload(BaseModel):
  data_file: str
  sector_map: str
  max_workers: int = 10
  chunk_size: int = 300
  timeout: int = 120
  fact_limit: int | None = None
  current_fact_limit: int | None = None
  top_k: int | None = None
  max_rows: int | None = None


@app.get("/api/options")
async def api_options():
  return {"datasets": DATASET_OPTIONS}


@app.post("/api/run")
async def api_start_run(payload: RunPayload, background_tasks: BackgroundTasks):
  record = RUN_MANAGER.create_run(payload.model_dump())
  background_tasks.add_task(RUN_MANAGER.execute_run, record)
  return {"run_id": record.run_id}


@app.get("/api/runs")
async def api_runs():
  return {"runs": serialize_runs(RUN_MANAGER.list_runs())}


@app.get("/api/runs/{run_id}")
async def api_run_detail(run_id: str):
  record = RUN_MANAGER.get_run(run_id)
  if not record:
    raise HTTPException(status_code=404, detail="Run not found")
  return {"run": record.to_dict()}


@app.get("/api/runs/{run_id}/results")
async def api_run_results(run_id: str):
  record = RUN_MANAGER.get_run(run_id)
  if not record:
    raise HTTPException(status_code=404, detail="Run not found")
  source = record.results_csv or record.live_results_path
  if not source or not Path(source).exists():
    return []
  df = pd.read_csv(source)
  cols = ["ticker", "quarter", "predicted_direction", "direction_score", "actual_return", "error"]
  for col in cols:
    if col not in df.columns:
      df[col] = ""
  clean_df = df[cols].replace({pd.NA: "", float("nan"): ""}).where(pd.notna(df), "")
  clean_df = clean_df.replace([float("inf"), float("-inf")], "")
  return JSONResponse(json.loads(clean_df.to_json(orient="records")))


@app.get("/api/runs/{run_id}/log")
async def api_run_log(run_id: str):
  record = RUN_MANAGER.get_run(run_id)
  if not record:
    raise HTTPException(status_code=404, detail="Run not found")
  text = RUN_MANAGER.read_log_tail(record)
  return {"log": text}


@app.get("/api/runs/{run_id}/kg")
async def api_run_kg(run_id: str, live: int = Query(0)):
  record = RUN_MANAGER.get_run(run_id)
  if not record:
    raise HTTPException(status_code=404, detail="Run not found")
  run_dir = RUN_MANAGER.get_run_directory(run_id)
  live_path = run_dir / "kg_live.html"
  final_path = record.kg_path
  if live and live_path.exists():
    return FileResponse(live_path, media_type="text/html")
  if final_path and Path(final_path).exists():
    return FileResponse(final_path, media_type="text/html")
  if live_path.exists():
    return FileResponse(live_path, media_type="text/html")
  raise HTTPException(status_code=404, detail="KG graph not available")


@app.delete("/api/history")
async def api_clear_history():
  import shutil
  for folder in ["token_logs", "timing_logs", "Results/web_runs"]:
    path = REPO_ROOT / folder
    if path.exists():
      for item in path.iterdir():
        if item.is_file():
          item.unlink(missing_ok=True)
        elif item.is_dir():
          shutil.rmtree(item, ignore_errors=True)
  return {"status": "ok"}

# ---- estimation helpers ----
def _dataset_info():
  info = []
  for ds in DATASET_OPTIONS:
    data_path = REPO_ROOT / ds["data_file"]
    rows = None
    if data_path.exists():
      try:
        rows = len(pd.read_csv(data_path))
      except Exception:
        rows = None
    info.append({**ds, "rows": rows})
  return info


def _stats_from_logs():
  token_path = REPO_ROOT / "token_logs" / "combined_token_usage.csv"
  timing_path = REPO_ROOT / "timing_logs" / "combined_timing.csv"
  avg_tokens = 20000
  avg_time = 10.0
  if token_path.exists():
    try:
      df = pd.read_csv(token_path)
      if not df.empty and "total_tokens" in df.columns:
        avg_tokens = df["total_tokens"].mean()
    except Exception:
      pass
  if timing_path.exists():
    try:
      df = pd.read_csv(timing_path)
      if not df.empty and "duration_seconds" in df.columns:
        avg_time = df["duration_seconds"].mean()
    except Exception:
      pass
  return avg_tokens, avg_time


@app.get("/api/estimate")
async def api_estimate(
  data_file: str,
  max_rows: int | None = None,
  top_k: int | None = None,
  fact_limit: int | None = None,
  current_fact_limit: int | None = None,
):
  datasets = _dataset_info()
  target = next((d for d in datasets if d["data_file"] == data_file), None)
  if not target:
    raise HTTPException(status_code=404, detail="data_file not found")
  rows = target.get("rows") or 0
  if max_rows is not None:
    rows = min(rows, max_rows)
  avg_tokens, avg_time = _stats_from_logs()
  # 基準：Top-K=5, fact_limit=8000, current_fact_limit=8000，並限制放大倍數避免誇張估算
  base_top_k = 5
  base_fact_limit = 8000
  base_curr_limit = 8000
  scale = 1.0
  if top_k:
    scale *= min(top_k / base_top_k, 2.0)
  if fact_limit:
    scale *= min(fact_limit / base_fact_limit, 2.0)
  if current_fact_limit:
    scale *= min(current_fact_limit / base_curr_limit, 2.0)
  total_tokens = avg_tokens * max(rows, 1) * scale
  est_cost = total_tokens * 0.00002  # 粗估 gpt-4o-mini 混合成本
  est_time = avg_time * max(rows, 1)
  return {
    "rows": rows,
    "avg_tokens_per_row": avg_tokens,
    "total_tokens": total_tokens,
    "estimated_cost_usd": est_cost,
    "estimated_time_seconds": est_time,
  }


@app.get("/api/runs/{run_id}/results.csv")
async def api_results_csv(run_id: str):
  record = RUN_MANAGER.get_run(run_id)
  if not record or not record.results_csv:
    raise HTTPException(status_code=404, detail="Results not available")
  return FileResponse(record.results_csv, media_type="text/csv")


@app.get("/api/runs/{run_id}/log/download")
async def api_log_file(run_id: str):
  record = RUN_MANAGER.get_run(run_id)
  if not record or not record.log_path or not Path(record.log_path).exists():
    raise HTTPException(status_code=404, detail="Log not available")
  return FileResponse(record.log_path, media_type="text/plain")


if FRONTEND_DIST.exists():
  app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
else:
  @app.get("/")
  async def spa_placeholder():
    return {"message": "前端尚未 build，請在 webapp/frontend 執行 `npm run build` 後重試。"}
