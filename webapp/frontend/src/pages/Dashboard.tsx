import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createRun, fetchOptions, fetchRuns } from '../api';
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
  const [maxWorkers, setMaxWorkers] = useState(1);
  const [chunkSize, setChunkSize] = useState(2);
  const [timeout, setTimeoutValue] = useState(120);
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
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? '啟動中...' : '開始跑'}
          </button>
        </form>
        {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      </section>

      <section className="card">
        <h2>既有執行</h2>
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
