import React from 'react';
import { Bot, GraduationCap, TrendingUp, Bell } from 'lucide-react';
import StatCard from '../components/StatCard';
import { useApi } from '../hooks/useApi';
import { apiFetch } from '../lib/api';
import { STUDENT_ID } from '../lib/constants';

export default function DashboardPage() {
  const { data: state, loading, error } = useApi<any>(() => apiFetch(`/api/state/${STUDENT_ID}`));

  if (loading) return <div className="page-container"><div className="spinner" /></div>;
  if (error || !state) return <div className="page-container">Failed to load dashboard</div>;

  const profile = state.profile || {};
  const skills = profile.skill_profile || {};
  const mastered = Object.values(skills).filter(v => v === "mastered").length;
  const weak = Object.values(skills).filter(v => v === "weak").length;
  
  const pendingReminders = (state.notifications || []).filter((n: any) => n.status === "pending").length;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-description">Welcome back! Here's an overview of your prep progress.</p>
      </div>

      <div className="grid-cards" style={{ marginBottom: '32px' }}>
        <StatCard 
          title="Skill Profile" 
          value={`${mastered} Mastered / ${weak} Weak`}
          icon={TrendingUp}
          to="/progress"
        />
        <StatCard 
          title="Pending Reminders" 
          value={pendingReminders}
          icon={Bell}
          to="/reminders"
        />
        <StatCard 
          title="Target Companies" 
          value={(profile.target_companies || []).length}
          icon={Bot}
          to="/profile"
        />
      </div>
      
      <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
        <div className="glass-panel" style={{ padding: '24px', flex: 1, minWidth: '300px' }}>
          <h3 style={{ marginBottom: '16px' }}>Recent Performance</h3>
          {state.performance_logs?.length > 0 ? (
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {state.performance_logs.slice(0, 3).map((l: any) => (
                <li key={l.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                  <span>{l.topic}</span>
                  <strong style={{ color: l.is_struggle ? 'var(--danger)' : l.is_mastery ? 'var(--success)' : 'inherit' }}>
                    {l.score}%
                  </strong>
                </li>
              ))}
            </ul>
          ) : (
             <p style={{ color: 'var(--text-secondary)' }}>No performance records yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
