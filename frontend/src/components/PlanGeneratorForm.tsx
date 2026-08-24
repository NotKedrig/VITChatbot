import React, { useState } from 'react';
import { Play } from 'lucide-react';

interface PlanGeneratorFormProps {
  onSubmit: (companies: string[], time: string, skills: string, msg: string) => Promise<void>;
  loading?: boolean;
}

export default function PlanGeneratorForm({ onSubmit, loading }: PlanGeneratorFormProps) {
  const [companies, setCompanies] = useState('');
  const [time, setTime] = useState('10 hours/week');
  const [skills, setSkills] = useState('');
  const [message, setMessage] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cList = companies.split(',').map(c => c.trim()).filter(Boolean);
    onSubmit(cList, time, skills, message);
  };

  return (
    <form onSubmit={handleSubmit} className="glass-panel" style={{ padding: '24px' }}>
      <h3 style={{ marginBottom: '16px' }}>Generate Study Plan</h3>
      
      <div className="form-group">
        <label className="form-label">Target Companies (comma separated)</label>
        <input 
          type="text" 
          className="form-input" 
          placeholder="e.g. NovaTech, Aether Robotics"
          value={companies} 
          onChange={e => setCompanies(e.target.value)}
          required
          disabled={loading}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Available Study Time</label>
        <input 
          type="text" 
          className="form-input" 
          placeholder="e.g. 15 hours per week"
          value={time} 
          onChange={e => setTime(e.target.value)}
          required
          disabled={loading}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Skills to Focus On</label>
        <input 
          type="text" 
          className="form-input" 
          placeholder="e.g. DSA, System Design"
          value={skills} 
          onChange={e => setSkills(e.target.value)}
          required
          disabled={loading}
        />
      </div>
      
      <div className="form-group">
        <label className="form-label">Additional Instructions (Optional)</label>
        <textarea 
          className="form-textarea" 
          placeholder="e.g. I need to focus on dynamic programming specifically."
          value={message} 
          onChange={e => setMessage(e.target.value)}
          disabled={loading}
        />
      </div>

      <button 
        type="submit" 
        className="glass-button primary" 
        disabled={loading || !companies || !time || !skills}
        style={{ width: '100%', justifyContent: 'center' }}
      >
        {loading ? <div className="spinner" /> : <><Play size={16} /> Generate Plan</>}
      </button>
    </form>
  );
}
