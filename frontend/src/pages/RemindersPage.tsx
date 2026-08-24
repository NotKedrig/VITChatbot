import React, { useState } from 'react';
import { Bell, Trash2 } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { STUDENT_ID } from '../lib/constants';
import { useApi } from '../hooks/useApi';
import ReminderForm from '../components/ReminderForm';
import EmptyState from '../components/EmptyState';

export default function RemindersPage() {
  const { data, loading, refetch } = useApi<any>(() => apiFetch(`/api/reminders/${STUDENT_ID}`));
  const [submitting, setSubmitting] = useState(false);

  const handleSchedule = async (message: string, isoDate: string) => {
    setSubmitting(true);
    try {
      await apiFetch('/api/reminders', {
        method: 'POST',
        body: JSON.stringify({ student_id: STUDENT_ID, message, due_at_iso: isoDate })
      });
      await refetch();
    } catch (err) {
      console.error(err);
      alert("Failed to schedule reminder");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiFetch(`/api/reminders/${id}`, { method: 'DELETE' });
      await refetch();
    } catch (err) {
      console.error(err);
      alert("Failed to delete reminder");
    }
  };

  if (loading) return <div className="page-container"><div className="spinner" /></div>;

  const reminders = data?.reminders || [];
  const pending = reminders.filter((r: any) => r.status === 'pending');
  const past = reminders.filter((r: any) => r.status !== 'pending');

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Reminders</h1>
        <p className="page-description">Manage your upcoming study sessions and important deadlines.</p>
      </div>

      <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div style={{ flex: '1 1 300px' }}>
          <ReminderForm onSubmit={handleSchedule} loading={submitting} />
        </div>
        
        <div style={{ flex: '2 1 500px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {pending.length > 0 ? (
            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ marginBottom: '16px' }}>Upcoming Reminders ({pending.length})</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {pending.map((r: any) => (
                  <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                    <div>
                      <div style={{ fontWeight: 500, marginBottom: '4px' }}>{r.message}</div>
                      <div style={{ fontSize: '13px', color: 'var(--accent-color)' }}>
                        {new Date(r.due_at).toLocaleString()}
                      </div>
                    </div>
                    <button 
                      className="glass-button" 
                      style={{ padding: '8px', color: 'var(--text-secondary)' }}
                      onClick={() => handleDelete(r.id)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState 
              icon={Bell}
              title="No upcoming reminders"
              description="Schedule a reminder to stay on track with your study plan."
            />
          )}

          {past.length > 0 && (
            <div className="glass-panel" style={{ padding: '24px', opacity: 0.7 }}>
              <h3 style={{ marginBottom: '16px', color: 'var(--text-secondary)' }}>Past & Cancelled</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {past.slice(0, 5).map((r: any) => (
                  <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', fontSize: '14px' }}>
                    <span style={{ textDecoration: r.status === 'cancelled' ? 'line-through' : 'none' }}>{r.message}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{r.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
