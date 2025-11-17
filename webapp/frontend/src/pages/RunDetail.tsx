import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchLog, fetchResults, fetchRun } from '../api';
import type { RunRecord, RunResultRow } from '../types';

export default function RunDetail() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [results, setResults] = useState<RunResultRow[]>([]);
  const [logText, setLogText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [kgUrl, setKgUrl] = useState<string>('');

  useEffect(() => {
    if (!runId) return;
    const poll = async () => {
      try {
        const [runResp, logResp, resultResp] = await Promise.all([
          fetchRun(runId),
          fetchLog(runId),
          fetchResults(runId),
        ]);
        setRun(runResp.run);
        if (runResp.run?.kg_path && !kgUrl) {
          setKgUrl(`/api/runs/${runId}/kg`);
        }
        setLogText((prev) => {
          const incoming = logResp.log;
          if (incoming.startsWith(prev)) {
            return prev + incoming.slice(prev.length);
          }
          return incoming;
        });
        setResults(resultResp);
      } catch (err) {
        setError((err as Error).message);
      }
    };
    poll();
    const timer = setInterval(poll, 4000);
    return () => clearInterval(timer);
  }, [runId, kgUrl]);

  if (!runId) {
    return <p>未指定 run ID</p>;
  }

  return (
    <div>
      <button className="btn-primary" onClick={() => navigate('/')}>
        ← 返回
      </button>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      <section className="card">
        <h2>Run {runId}</h2>
        {run ? (
          <>
            <p>
              狀態：<span className={`status-tag status-${run.status}`}>{run.status}</span>
            </p>
            <p>
              進度：{run.completed_rows}/{run.total_rows ?? '?'}
            </p>
            <progress value={run.completed_rows} max={run.total_rows ?? 1} style={{ width: '100%' }} />
            <p>資料檔：{run.config?.data_file}</p>
            <p>Sector map：{run.config?.sector_map}</p>
            {run.error && <p style={{ color: '#b91c1c' }}>錯誤：{run.error}</p>}
          </>
        ) : (
          <p>載入中...</p>
        )}
      </section>

      <section className="card">
        <h2>Predictions</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Quarter</th>
              <th>Direction</th>
              <th>Score</th>
              <th>Actual Return</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {results.map((row) => (
              <tr key={`${row.ticker}-${row.quarter}`}>
                <td>{row.ticker}</td>
                <td>{row.quarter}</td>
                <td>{row.predicted_direction}</td>
                <td>{row.direction_score ?? '-'}</td>
                <td>{row.actual_return?.toFixed(4)}</td>
                <td>{row.error}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Knowledge Graph</h2>
        {run && (run.kg_path || run.status === 'running') ? (
          kgUrl ? <iframe src={kgUrl} title="kg" className="kg-frame" /> : <p>KG 已生成，請稍候載入...</p>
        ) : (
          <p>尚未產生 KG</p>
        )}
      </section>

      <section className="card">
        <h2>Log</h2>
        <pre className="log-area">{logText}</pre>
      </section>
    </div>
  );
}
