import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Info } from 'lucide-react';
import { API_BASE } from '../lib/api';

interface ChatPanelProps {
  studentId: string;
  threadId: string;
  onPlanUpdate: (plan: any) => void;
}

export default function ChatPanel({ studentId, threadId, onPlanUpdate }: ChatPanelProps) {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activityIndicator, setActivityIndicator] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Load initial thread state
    fetch(`${API_BASE}/api/thread/${threadId}`)
      .then(res => res.json())
      .then(data => {
        if (data.messages) setMessages(data.messages);
        if (data.current_plan) onPlanUpdate(data.current_plan);
      })
      .catch(e => console.error(e));
  }, [threadId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);
    setActivityIndicator('Routing...');

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg.content, thread_id: threadId, student_id: studentId })
      });
      
      const data = await res.json();
      
      if (data.next_agent) {
        setActivityIndicator(`Supervisor → ${data.next_agent.replace('_', ' ')}`);
      }

      setMessages(data.messages || []);
      if (data.current_plan) {
        onPlanUpdate(data.current_plan);
      }
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'agent', content: '❌ Backend connection failed.' }]);
    } finally {
      setIsLoading(false);
      setTimeout(() => setActivityIndicator(null), 2000);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
      
      {/* Activity Indicator */}
      {activityIndicator && (
        <div className="animate-in" style={{ 
          position: 'absolute', top: 16, right: 24, 
          background: 'var(--accent-glow)', padding: '6px 12px', 
          borderRadius: 20, fontSize: '0.85em', display: 'flex', alignItems: 'center', gap: 6,
          backdropFilter: 'blur(4px)', border: '1px solid var(--accent-color)'
        }}>
          <Loader2 size={14} className="spinner" style={{ borderTopColor: '#fff', border: 0 }} />
          {activityIndicator}
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '8px' }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ 
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '80%',
            background: msg.role === 'user' ? 'var(--accent-color)' : 'var(--bg-glass-hover)',
            padding: '12px 16px',
            borderRadius: '16px',
            borderBottomRightRadius: msg.role === 'user' ? '4px' : '16px',
            borderBottomLeftRadius: msg.role === 'agent' || msg.role === 'assistant' ? '4px' : '16px',
            border: msg.role !== 'user' ? '1px solid var(--border-glass)' : 'none',
          }}>
            <div className="prose" style={{ whiteSpace: 'pre-wrap' }}>
              {msg.content}
            </div>
            {msg.role !== 'user' && msg.citations && msg.citations.length > 0 && (
              <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: '0.85em', color: 'var(--text-secondary)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '8px' }}>
                  <Info size={14} /> <strong>Sources:</strong>
                </div>
                <ul style={{ paddingLeft: '20px', margin: 0 }}>
                  {msg.citations.map((cite: any, idx: number) => (
                    <li key={idx}>[{idx+1}] {cite.source_id} (Relevance: {(cite.relevance_score * 100).toFixed(1)}%)</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div style={{ alignSelf: 'flex-start', padding: '12px 16px', background: 'var(--bg-glass-hover)', borderRadius: '16px', border: '1px solid var(--border-glass)' }}>
            <div className="spinner"></div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <input 
          type="text" 
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask a question or report progress..."
          style={{ 
            flex: 1, background: 'var(--bg-glass)', border: '1px solid var(--border-glass)', 
            color: 'var(--text-primary)', padding: '14px 16px', borderRadius: '12px',
            outline: 'none', fontFamily: 'inherit', fontSize: '1em'
          }}
          disabled={isLoading}
        />
        <button type="submit" className="glass-button primary" disabled={isLoading || !input.trim()}>
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
