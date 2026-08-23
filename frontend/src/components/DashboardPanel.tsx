import React from 'react';
import { User, Bell, Target, TrendingUp, AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function DashboardPanel({ state }: { state: any }) {
  if (!state) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
        <div className="spinner" style={{ margin: '0 auto 12px' }}></div>
        Loading dashboard...
      </div>
    );
  }

  const { profile, performance_logs, notifications } = state;
  const skills = profile?.skill_profile || {};
  const targets = profile?.target_companies || [];
  const pendingNotifs = notifications?.filter((n: any) => n.status === 'pending') || [];

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* Profile Section */}
      <section>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '0.9em', textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
          <User size={16} /> Student Profile
        </h3>
        <div style={{ background: 'var(--bg-glass-hover)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-glass)' }}>
          <div style={{ marginBottom: '12px' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85em' }}>ID:</span> {profile?.student_id}
          </div>
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85em' }}>Targets:</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {targets.length > 0 ? targets.map((t: string) => (
              <span key={t} style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', padding: '4px 10px', borderRadius: '12px', fontSize: '0.8em' }}>{t}</span>
            )) : <span style={{ color: 'var(--text-secondary)', fontSize: '0.85em' }}>None set</span>}
          </div>
        </div>
      </section>

      {/* Skills / Performance */}
      <section>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '0.9em', textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
          <Target size={16} /> Skill Mastery
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {Object.keys(skills).length > 0 ? Object.entries(skills).map(([topic, status]: any) => (
            <div key={topic} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-glass-hover)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-glass)' }}>
              <span style={{ fontSize: '0.9em' }}>{topic.replace('_', ' ')}</span>
              {status === 'mastered' ? (
                <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8em' }}><CheckCircle2 size={14} /> Mastered</span>
              ) : status === 'weak' ? (
                <span style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8em' }}><AlertTriangle size={14} /> Weak</span>
              ) : (
                <span style={{ color: 'var(--warning)', fontSize: '0.8em' }}>Intermediate</span>
              )}
            </div>
          )) : (
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85em' }}>No skills assessed yet.</div>
          )}
        </div>
      </section>

      {/* Notifications */}
      <section>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '0.9em', textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
          <Bell size={16} /> Reminders ({pendingNotifs.length})
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {pendingNotifs.map((n: any) => (
            <div key={n.id} style={{ background: 'var(--bg-glass-hover)', padding: '12px', borderRadius: '8px', borderLeft: '3px solid var(--accent-color)' }}>
              <div style={{ fontSize: '0.9em', marginBottom: '4px' }}>{n.message}</div>
              <div style={{ fontSize: '0.75em', color: 'var(--text-secondary)' }}>{new Date(n.due_at).toLocaleString()}</div>
            </div>
          ))}
          {pendingNotifs.length === 0 && (
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85em' }}>No pending reminders.</div>
          )}
        </div>
      </section>

    </div>
  );
}
