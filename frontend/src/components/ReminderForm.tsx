import React, { useState } from 'react';
import { Bell } from 'lucide-react';

interface ReminderFormProps {
  onSubmit: (message: string, isoDate: string) => Promise<void>;
  loading?: boolean;
}

export default function ReminderForm({ onSubmit, loading }: ReminderFormProps) {
  const [message, setMessage] = useState('');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message || !date || !time) return;
    
    // Combine date and time into ISO
    const localDate = new Date(`${date}T${time}`);
    onSubmit(message, localDate.toISOString());
    setMessage('');
  };

  return (
    <form onSubmit={handleSubmit} className="glass-panel" style={{ padding: '24px' }}>
      <h3 style={{ marginBottom: '16px' }}>Set Reminder</h3>
      
      <div className="form-group">
        <label className="form-label">Message</label>
        <input 
          type="text" 
          className="form-input" 
          placeholder="e.g. Revise OS paging"
          value={message} 
          onChange={e => setMessage(e.target.value)}
          required
          disabled={loading}
        />
      </div>

      <div style={{ display: 'flex', gap: '16px' }}>
        <div className="form-group" style={{ flex: 1 }}>
          <label className="form-label">Date</label>
          <input 
            type="date" 
            className="form-input" 
            value={date} 
            onChange={e => setDate(e.target.value)}
            required
            disabled={loading}
          />
        </div>
        <div className="form-group" style={{ flex: 1 }}>
          <label className="form-label">Time</label>
          <input 
            type="time" 
            className="form-input" 
            value={time} 
            onChange={e => setTime(e.target.value)}
            required
            disabled={loading}
          />
        </div>
      </div>

      <button 
        type="submit" 
        className="glass-button primary" 
        disabled={loading || !message || !date || !time}
        style={{ width: '100%', justifyContent: 'center' }}
      >
        {loading ? <div className="spinner" /> : <><Bell size={16} /> Schedule</>}
      </button>
    </form>
  );
}
