import React, { useState } from 'react';
import { TOPICS } from '../lib/constants';
import { Send } from 'lucide-react';

interface ScoreFormProps {
  onSubmit: (topic: string, score: number) => Promise<void>;
  loading?: boolean;
}

export default function ScoreForm({ onSubmit, loading }: ScoreFormProps) {
  const [topic, setTopic] = useState(TOPICS[0]);
  const [score, setScore] = useState<number>(0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(topic, score);
  };

  return (
    <form onSubmit={handleSubmit} className="glass-panel" style={{ padding: '24px' }}>
      <h3 style={{ marginBottom: '16px' }}>Submit Test Score</h3>
      
      <div className="form-group">
        <label className="form-label">Topic</label>
        <select 
          className="form-select" 
          value={topic} 
          onChange={e => setTopic(e.target.value)}
          disabled={loading}
        >
          {TOPICS.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div className="form-group">
        <label className="form-label">Score (%)</label>
        <input 
          type="number" 
          className="form-input" 
          min="0" max="100" 
          value={score} 
          onChange={e => setScore(Number(e.target.value))}
          disabled={loading}
        />
      </div>

      <button 
        type="submit" 
        className="glass-button primary" 
        disabled={loading}
        style={{ width: '100%', justifyContent: 'center' }}
      >
        {loading ? <div className="spinner" /> : <><Send size={16} /> Submit Score</>}
      </button>
    </form>
  );
}
