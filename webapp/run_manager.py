from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from . import REPO_ROOT


WEB_RUN_ROOT = REPO_ROOT / "Results" / "web_runs"
WEB_RUN_ROOT.mkdir(parents=True, exist_ok=True)
METADATA_FILE = "run.json"


@dataclass
class RunRecord:
    run_id: str
    config: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    status: str = "queued"  # queued -> running -> completed/failed
    log_path: Path | None = None
    results_csv: Path | None = None  # finalized copy
    live_results_path: Path | None = None  # direct orchestrator output during run
    kg_path: Path | None = None
    error: Optional[str] = None
    finished_at: Optional[float] = None
    total_rows: Optional[int] = None
    completed_rows: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "config": self.config,
            "created_at": self.created_at,
            "status": self.status,
            "log_path": str(self.log_path) if self.log_path else None,
            "results_csv": str(self.results_csv) if self.results_csv else None,
            "kg_path": str(self.kg_path) if self.kg_path else None,
            "live_results_path": str(self.live_results_path) if self.live_results_path else None,
            "error": self.error,
            "finished_at": self.finished_at,
            "total_rows": self.total_rows,
            "completed_rows": self.completed_rows,
        }


class RunManager:
    def __init__(self) -> None:
        self._runs: Dict[str, RunRecord] = {}
        self._lock = threading.Lock()
        self._load_existing_runs()

    def _metadata_path(self, run_id: str) -> Path:
        return WEB_RUN_ROOT / run_id / METADATA_FILE

    def _load_existing_runs(self) -> None:
        for run_dir in WEB_RUN_ROOT.iterdir():
            if not run_dir.is_dir():
                continue
            meta_path = run_dir / METADATA_FILE
            if not meta_path.exists():
                continue
            try:
                data = json.loads(meta_path.read_text())
                record = RunRecord(
                    run_id=data["run_id"],
                    config=data["config"],
                    created_at=data.get("created_at", time.time()),
                    status=data.get("status", "completed"),
                    log_path=Path(data["log_path"]) if data.get("log_path") else None,
                    results_csv=Path(data["results_csv"]) if data.get("results_csv") else None,
                    live_results_path=Path(data["live_results_path"]) if data.get("live_results_path") else None,
                    kg_path=Path(data["kg_path"]) if data.get("kg_path") else None,
                    error=data.get("error"),
                    finished_at=data.get("finished_at"),
                    total_rows=data.get("total_rows"),
                    completed_rows=data.get("completed_rows", 0),
                )
                self._runs[record.run_id] = record
            except Exception:
                continue

    def _save_metadata(self, record: RunRecord) -> None:
        meta_path = self._metadata_path(record.run_id)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))

    def _commit(self, record: RunRecord) -> None:
        with self._lock:
            self._runs[record.run_id] = record
        self._save_metadata(record)

    def get_run_directory(self, run_id: str) -> Path:
        return WEB_RUN_ROOT / run_id

    def _generate_kg(self, source_csv: Path, target: Path) -> None:
        if not source_csv.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                sys.executable,
                "scripts/generate_sample_kg.py",
                "--input",
                str(source_csv),
                "--output",
                str(target),
            ],
            cwd=str(REPO_ROOT),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _refresh_live_kg(self, record: RunRecord, source: Path, *, final: bool) -> None:
        run_dir = self.get_run_directory(record.run_id)
        target = run_dir / ("kg_graph.html" if final else "kg_live.html")
        self._generate_kg(source, target)
        if final:
            record.kg_path = target
            self._commit(record)

    def list_runs(self) -> list[RunRecord]:
        with self._lock:
            return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            return self._runs.get(run_id)

    def _resolve_path(self, path_str: str) -> Path:
        path = Path(path_str)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path

    def _count_csv_rows(self, csv_path: Path) -> Optional[int]:
        if not csv_path.exists():
            return None
        try:
            df = pd.read_csv(csv_path)
            return int(len(df))
        except Exception:
            return None

    def create_run(self, config: Dict[str, Any]) -> RunRecord:
        run_id = uuid.uuid4().hex[:8]
        run_path = WEB_RUN_ROOT / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        log_path = run_path / "run.log"
        data_path = self._resolve_path(config["data_file"])
        sector_map_path = self._resolve_path(config["sector_map"])
        total_rows = self._count_csv_rows(data_path)
        live_results = REPO_ROOT / f"{data_path.stem}_results.csv"
        normalized_config = {
            **config,
            "data_file": str(data_path),
            "sector_map": str(sector_map_path),
        }
        record = RunRecord(
            run_id=run_id,
            config=normalized_config,
            log_path=log_path,
            total_rows=total_rows,
            live_results_path=live_results,
        )
        self._commit(record)
        return record

    # ------------------------------------------------------------------
    def execute_run(self, record: RunRecord) -> None:
        """Run the orchestrator script and capture logs."""
        record.status = "running"
        self._commit(record)
        run_path = WEB_RUN_ROOT / record.run_id
        config = record.config
        data_path = Path(config["data_file"])
        sector_map = Path(config["sector_map"])
        max_workers = str(config["max_workers"])
        chunk_size = str(config["chunk_size"])
        timeout = str(config["timeout"])

        cmd = [
            sys.executable,
            "orchestrator_parallel_facts.py",
            "--data",
            str(data_path),
            "--sector-map",
            str(sector_map),
            "--max-workers",
            max_workers,
            "--chunk-size",
            chunk_size,
            "--timeout",
            timeout,
        ]
        generated_csv = record.live_results_path or (REPO_ROOT / f"{data_path.stem}_results.csv")
        if generated_csv.exists():
            generated_csv.unlink()
        generated_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=[
                "ticker",
                "quarter",
                "parsed_and_analyzed_facts",
                "research_note",
                "actual_return",
                "predicted_direction",
                "direction_score",
                "error",
            ]
        ).to_csv(generated_csv, index=False)

        stop_event = threading.Event()
        monitor_thread = threading.Thread(
            target=self._monitor_results,
            args=(record, generated_csv, stop_event),
            daemon=True,
        )
        monitor_thread.start()
        try:
            with open(record.log_path, "w") as log_file:
                process = subprocess.Popen(
                    cmd,
                    cwd=str(REPO_ROOT),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
                ret = process.wait()
            stop_event.set()
            monitor_thread.join()
            if ret != 0:
                record.status = "failed"
                record.error = f"Orchestrator exited with code {ret}"
                record.finished_at = time.time()
                self._commit(record)
                return

            if generated_csv.exists():
                dest_csv = run_path / "results.csv"
                shutil.copy(generated_csv, dest_csv)
                record.results_csv = dest_csv
                record.live_results_path = dest_csv
                try:
                    self._refresh_live_kg(record, dest_csv, final=True)
                except Exception as exc:
                    record.error = f"KG generation failed: {exc}"
            else:
                record.error = f"Expected results file not found: {generated_csv}"

            if record.total_rows is not None:
                record.completed_rows = record.total_rows
            record.status = "completed" if not record.error else "completed_with_warnings"
        except Exception as exc:  # pragma: no cover - catch-all for runtime issues
            record.status = "failed"
            record.error = str(exc)
        finally:
            record.finished_at = time.time()
            self._commit(record)

    def load_results_preview(self, record: RunRecord, limit: int = 50) -> list[Dict[str, Any]]:
        source = (
            record.results_csv
            if record.results_csv and record.results_csv.exists()
            else record.live_results_path
        )
        if not source or not source.exists():
            return []
        df = pd.read_csv(source)
        desired_cols = [
            "ticker",
            "quarter",
            "predicted_direction",
            "direction_score",
            "actual_return",
            "error",
        ]
        available = [c for c in desired_cols if c in df.columns]
        data = df[available].copy()
        for col in desired_cols:
            if col not in data.columns:
                data[col] = ""
        ordered = data[desired_cols].fillna("").head(limit)
        return ordered.to_dict(orient="records")

    def read_log_tail(self, record: RunRecord, max_bytes: int = 16000) -> str:
        if not record.log_path or not record.log_path.exists():
            return ""
        with open(record.log_path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            return fh.read().decode(errors="ignore")

    def _monitor_results(self, record: RunRecord, results_path: Path, stop_event: threading.Event, interval: float = 2.0) -> None:
        last_value = record.completed_rows
        while not stop_event.is_set():
            if results_path.exists():
                rows = self._count_csv_rows(results_path)
                if rows is not None and rows >= 0:
                    if rows != record.completed_rows:
                        record.completed_rows = rows
                        self._commit(record)
                        if record.live_results_path:
                            self._refresh_live_kg(record, Path(record.live_results_path), final=False)
            stop_event.wait(interval)


RUN_MANAGER = RunManager()
