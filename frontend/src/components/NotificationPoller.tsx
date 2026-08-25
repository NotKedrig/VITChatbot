import React, { useEffect, useState, useRef } from 'react';
import { apiFetch } from '../lib/api';
import { STUDENT_ID } from '../lib/constants';
import { Bell, X } from 'lucide-react';

export default function NotificationPoller() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const seenIds = useRef<Set<number>>(new Set());
  const initialFetchDone = useRef(false);

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await apiFetch(`/api/reminders/${STUDENT_ID}`);
        if (data && data.reminders) {
          const dispatched = data.reminders.filter((r: any) => r.status === 'dispatched');
          
          if (!initialFetchDone.current) {
            // First time, just record seen ones to not spam old alerts
            dispatched.forEach((r: any) => seenIds.current.add(r.id));
            initialFetchDone.current = true;
          } else {
            // Find newly dispatched
            const newAlerts = dispatched.filter((r: any) => !seenIds.current.has(r.id));
            if (newAlerts.length > 0) {
              newAlerts.forEach((r: any) => seenIds.current.add(r.id));
              setAlerts(prev => [...prev, ...newAlerts]);
            }
          }
        }
      } catch (e) {
        console.error('Failed to poll notifications', e);
      }
    };

    poll();
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, []);

  const dismiss = (id: number) => {
    setAlerts(prev => prev.filter(a => a.id !== id));
  };

  if (alerts.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      top: '20px',
      right: '20px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '10px'
    }}>
      {alerts.map(a => (
        <div key={a.id} className="glass-panel" style={{
          padding: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          minWidth: '300px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          animation: 'slideIn 0.3s ease-out'
        }}>
          <div style={{ color: 'var(--accent-color)' }}>
            <Bell size={24} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: '14px' }}>Reminder!</div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{a.message}</div>
          </div>
          <button onClick={() => dismiss(a.id)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <X size={16} />
          </button>
        </div>
      ))}
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
