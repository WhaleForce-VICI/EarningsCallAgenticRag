import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createRun, fetchOptions, fetchRuns, estimateRun, clearHistory } from '../api';
import type { DatasetOption, RunRecord } from '../types';

function formatDate(ts?: number) {
  if (!ts) return '-';
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) {
    return new Date(ts).toLocaleString();
  }
  return d.toLocaleString();
}

export default function Dashboard() {
  const [datasets, setDatasets] = useState<DatasetOption[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>('');
  const [maxWorkers, setMaxWorkers] = useState(10);
  const [chunkSize, setChunkSize] = useState(300);
  const [timeout, setTimeoutValue] = useState(120);
  const [factLimit, setFactLimit] = useState<number | ''>(0);
  const [currFactLimit, setCurrFactLimit] = useState<number | ''>(0);
  const [topK, setTopK] = useState<number | ''>(5);
  const [maxRows, setMaxRows] = useState<number | ''>('');
  const [estimate, setEstimate] = useState<any | null>(null);
  const [totalRows, setTotalRows] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchOptions()
      .then((res) => {
        setDatasets(res.datasets);
        if (res.datasets.length > 0) {
          setSelectedDataset(res.datasets[0].data_file);
        }
      })
      .catch((err) => setError(err.message));
    fetchRuns()
      .then((res) => setRuns(res.runs))
      .catch((err) => setError(err.message));
  }, []);

  // 當資料集/前N筆/TopK 變更時自動估算
  useEffect(() => {
    const doEstimate = async () => {
      try {
        if (!selectedDataset) return;
        const est = await estimateRun(
          selectedDataset,
          maxRows ? Number(maxRows) : undefined,
          topK ? Number(topK) : undefined,
          factLimit ? Number(factLimit) : undefined,
          currFactLimit ? Number(currFactLimit) : undefined,
        );
        setEstimate(est);
        setTotalRows(est.rows);
      } catch (err) {
        setError((err as Error).message);
      }
    };
    doEstimate();
  }, [selectedDataset, maxRows, topK, factLimit, currFactLimit]);

  const datasetMap = useMemo(() => {
    const map: Record<string, DatasetOption> = {};
    datasets.forEach((ds) => {
      map[ds.data_file] = ds;
    });
    return map;
  }, [datasets]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    const ds = datasetMap[selectedDataset];
    if (!ds) {
      setError('請選擇資料集');
      return;
    }
    setLoading(true);
    try {
      const resp = await createRun({
        data_file: ds.data_file,
        sector_map: ds.sector_map,
        max_workers: maxWorkers,
        chunk_size: chunkSize,
        timeout,
        fact_limit: factLimit || undefined,
        current_fact_limit: currFactLimit || undefined,
        top_k: topK || undefined,
        max_rows: maxRows || undefined,
      });
      navigate(`/runs/${resp.run_id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <section className="card">
        <h2>建立新任務</h2>
        <form className="grid-form" onSubmit={handleSubmit}>
          <label>
            資料集
            <select value={selectedDataset} onChange={(e) => setSelectedDataset(e.target.value)}>
              {datasets.map((ds) => (
                <option key={ds.data_file} value={ds.data_file}>
                  {ds.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Max workers
            <input type="number" min={1} value={maxWorkers} onChange={(e) => setMaxWorkers(Number(e.target.value))} />
          </label>
          <label>
            Chunk size
            <input type="number" min={1} value={chunkSize} onChange={(e) => setChunkSize(Number(e.target.value))} />
          </label>
          <label>
            Timeout (秒)
            <input type="number" min={60} value={timeout} onChange={(e) => setTimeoutValue(Number(e.target.value))} />
          </label>
          <label>
            Transcript facts 上限 (0=不截斷)
            <input type="number" min={0} value={factLimit} onChange={(e) => setFactLimit(e.target.value ? Number(e.target.value) : '')} />
          </label>
          <label>
            當季財報 facts 上限 (0=不截斷)
            <input type="number" min={0} value={currFactLimit} onChange={(e) => setCurrFactLimit(e.target.value ? Number(e.target.value) : '')} />
          </label>
          <label>
            Top-K
            <input type="number" min={1} value={topK} onChange={(e) => setTopK(e.target.value ? Number(e.target.value) : '')} />
          </label>
          <label>
            僅處理前 N 筆
            <input
              type="number"
              min={1}
              placeholder={totalRows ? `預設=${totalRows}` : ''}
              value={maxRows}
              onChange={(e) => setMaxRows(e.target.value ? Number(e.target.value) : '')}
            />
          </label>
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? '啟動中...' : '開始跑'}
          </button>
          <button
            className="btn-secondary"
            type="button"
            onClick={async () => {
              try {
                const est = await estimateRun(selectedDataset, maxRows ? Number(maxRows) : undefined);
                setEstimate(est);
              } catch (err) {
                setError((err as Error).message);
              }
            }}
          >
            預估時間/費用
          </button>
        </form>
        {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
        {estimate && (
          <div style={{ marginTop: '0.5rem' }}>
            <div>Rows: {estimate.rows}</div>
            <div>估計 tokens/row: {Math.round(estimate.avg_tokens_per_row)}</div>
            <div>總 tokens: {Math.round(estimate.total_tokens)}</div>
            <div>估計費用: ${estimate.estimated_cost_usd.toFixed(4)}</div>
            <div>估計時間: {estimate.estimated_time_seconds.toFixed(1)} 秒</div>
          </div>
        )}
      </section>

      <section className="card">
        <h2>既有執行</h2>
        <button
          className="btn-secondary"
          type="button"
          onClick={async () => {
            setError(null);
            try {
              await clearHistory();
              setRuns([]);
            } catch (err) {
              setError((err as Error).message);
            }
          }}
          style={{ marginBottom: '0.75rem' }}
        >
          清除歷史紀錄
        </button>
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>資料集</th>
              <th>狀態</th>
              <th>進度</th>
              <th>建立</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.run_id} onClick={() => navigate(`/runs/${run.run_id}`)}>
                <td>{run.run_id}</td>
                <td>{run.config?.data_file}</td>
                <td>
                  <span className={`status-tag status-${run.status}`}>{run.status}</span>
                </td>
                <td>
                  {run.completed_rows}/{run.total_rows ?? '?'}
                </td>
                <td>{formatDate(run.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
