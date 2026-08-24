import React, { useState, useEffect } from 'react';
import { User, Save } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { STUDENT_ID } from '../lib/constants';
import { useApi } from '../hooks/useApi';

export default function ProfilePage() {
  const { data: state, loading, refetch } = useApi<any>(() => apiFetch(`/api/state/${STUDENT_ID}`));
  const [companies, setCompanies] = useState('');
  const [time, setTime] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (state?.profile) {
      setCompanies((state.profile.target_companies || []).join(', '));
      setTime(state.profile.available_time || '');
    }
  }, [state]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await apiFetch(`/api/profile/${STUDENT_ID}`, {
        method: 'PUT',
        body: JSON.stringify({
          target_companies: companies.split(',').map(c => c.trim()).filter(Boolean),
          available_time: time
        })
      });
      await refetch();
      alert("Profile updated!");
    } catch (err) {
      console.error(err);
      alert("Failed to update profile");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="page-container"><div className="spinner" /></div>;

  const skills = state?.profile?.skill_profile || {};

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Student Profile</h1>
        <p className="page-description">Manage your preferences and view your current skill mastery.</p>
      </div>

      <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <form onSubmit={handleSave} className="glass-panel" style={{ padding: '32px', flex: '1 1 400px' }}>
          <h3 style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <User size={20} color="var(--accent-color)" /> General Info
          </h3>
          
          <div className="form-group">
            <label className="form-label">Student ID (Read-only)</label>
            <input type="text" className="form-input" value={STUDENT_ID} disabled style={{ opacity: 0.7 }} />
          </div>

          <div className="form-group">
            <label className="form-label">Target Companies (comma separated)</label>
            <input 
              type="text" 
              className="form-input" 
              value={companies} 
              onChange={e => setCompanies(e.target.value)}
              disabled={saving}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Available Study Time</label>
            <input 
              type="text" 
              className="form-input" 
              value={time} 
              onChange={e => setTime(e.target.value)}
              disabled={saving}
            />
          </div>

          <button type="submit" className="glass-button primary" disabled={saving}>
            {saving ? <div className="spinner" /> : <><Save size={16} /> Save Changes</>}
          </button>
        </form>

        <div className="glass-panel" style={{ padding: '32px', flex: '1 1 400px' }}>
          <h3 style={{ marginBottom: '24px' }}>Computed Skill Profile</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
            Your skill profile is automatically updated based on your progress submissions.
          </p>
          
          {Object.keys(skills).length > 0 ? (
            <div style={{ display: 'grid', gap: '12px' }}>
              {Object.entries(skills).map(([skill, level]) => (
                <div key={skill} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                  <span style={{ fontWeight: 500 }}>{skill}</span>
                  <span style={{ 
                    fontSize: '12px', 
                    padding: '4px 12px', 
                    borderRadius: '12px',
                    textTransform: 'capitalize',
                    background: level === 'mastered' ? 'rgba(16,185,129,0.1)' : level === 'weak' ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.05)',
                    color: level === 'mastered' ? 'var(--success)' : level === 'weak' ? 'var(--danger)' : 'var(--text-secondary)'
                  }}>
                    {level as string}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)', background: 'rgba(0,0,0,0.1)', borderRadius: '8px' }}>
              No skills tracked yet. Submit progress to build your profile.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
