import { Navigate, Route, Routes } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import RunDetail from './pages/RunDetail';
import './App.css';

function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Earnings Call Agentic RAG</h1>
          <p>啟動任務、追蹤進度、檢視 KG — 全部在同一個 SPA 介面。</p>
        </div>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
