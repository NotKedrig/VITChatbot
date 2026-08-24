import React from 'react';
import { useApi } from '../hooks/useApi';
import { apiFetch } from '../lib/api';

interface StatusData {
  database: boolean;
  knowledge_base: boolean;
  scheduler: boolean;
  gemini: boolean;
}

export default function SystemStatus() {
  const { data, loading } = useApi<StatusData>(() => apiFetch('/api/health/status'));

  if (loading || !data) {
    return <div className="status-indicator">Checking system...</div>;
  }

  const items = [
    { label: "Local KB", ok: data.knowledge_base },
    { label: "Database", ok: data.database },
    { label: "Scheduler", ok: data.scheduler },
    { label: "Gemini API", ok: data.gemini }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-secondary)', fontWeight: 600, padding: '0 8px' }}>
        System Status
      </div>
      {items.map(item => (
        <div key={item.label} className="status-indicator">
          <div className={`status-dot ${item.ok ? 'online' : 'offline'}`} />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}
