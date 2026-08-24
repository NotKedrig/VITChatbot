import React, { useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { STUDENT_ID } from '../lib/constants';
import { useApi } from '../hooks/useApi';
import ScoreForm from '../components/ScoreForm';
import EmptyState from '../components/EmptyState';

export default function ProgressPage() {
  const { data, loading, refetch } = useApi<any>(() => apiFetch(`/api/progress/${STUDENT_ID}`));
  const [submitting, setSubmitting] = useState(false);

  const handleSubmitScore = async (topic: string, score: number) => {
    setSubmitting(true);
    try {
      const res = await apiFetch<any>('/api/progress/submit', {
        method: 'POST',
        body: JSON.stringify({ student_id: STUDENT_ID, topic, score })
      });
      if (res.signal !== "neutral") {
        alert(`Skill level updated due to ${res.signal} signal in ${topic}!`);
      }
      await refetch();
    } catch (err) {
      console.error(err);
      alert("Failed to submit score");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="page-container"><div className="spinner" /></div>;

  const logs = data?.logs || [];

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Progress Tracking</h1>
        <p className="page-description">Log your test scores and track your skill mastery over time.</p>
      </div>

      <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div style={{ flex: '1 1 300px' }}>
          <ScoreForm onSubmit={handleSubmitScore} loading={submitting} />
        </div>
        
        <div style={{ flex: '2 1 500px' }}>
          {logs.length > 0 ? (
            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ marginBottom: '16px' }}>Performance History</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {logs.map((log: any, idx: number) => (
                  <div key={idx} style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    padding: '16px', 
                    background: 'rgba(255,255,255,0.05)', 
                    borderRadius: '8px',
                    borderLeft: log.is_struggle ? '4px solid var(--danger)' : log.is_mastery ? '4px solid var(--success)' : '4px solid transparent'
                  }}>
                    <div>
                      <div style={{ fontWeight: 500, marginBottom: '4px' }}>{log.topic}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {new Date(log.timestamp).toLocaleString()}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      {log.is_struggle && <span style={{ fontSize: '12px', color: 'var(--danger)', background: 'rgba(239,68,68,0.1)', padding: '2px 8px', borderRadius: '12px' }}>Struggle</span>}
                      {log.is_mastery && <span style={{ fontSize: '12px', color: 'var(--success)', background: 'rgba(16,185,129,0.1)', padding: '2px 8px', borderRadius: '12px' }}>Mastery</span>}
                      <strong style={{ fontSize: '18px' }}>{log.score}%</strong>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState 
              icon={TrendingUp}
              title="No scores logged"
              description="Submit your first mock test or practice score using the form to start tracking your progress."
            />
          )}
        </div>
      </div>
    </div>
  );
}
