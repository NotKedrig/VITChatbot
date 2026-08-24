import React, { useState } from 'react';
import { Search } from 'lucide-react';
import { apiFetch } from '../lib/api';
import OfflineBanner from '../components/OfflineBanner';
import EvidenceCard from '../components/EvidenceCard';
import EmptyState from '../components/EmptyState';

export default function CompanyResearchPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch<any>('/api/research', {
        method: 'POST',
        body: JSON.stringify({ query })
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Company Research</h1>
        <p className="page-description">Search the knowledge base for specific company eligibility, prep guides, and interview details.</p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '12px', marginBottom: '32px' }}>
        <input
          type="text"
          className="form-input"
          placeholder="e.g. What is the CGPA cutoff for NovaTech?"
          value={query}
          onChange={e => setQuery(e.target.value)}
          disabled={loading}
          style={{ flex: 1 }}
        />
        <button type="submit" className="glass-button primary" disabled={loading || !query}>
          {loading ? <div className="spinner" /> : <><Search size={16} /> Search</>}
        </button>
      </form>

      {error && <div className="banner warning">{error}</div>}

      {result ? (
        <div className="animate-in">
          {result.is_offline && <OfflineBanner />}
          
          {result.answer && (
            <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
              <h3 style={{ marginBottom: '16px', color: 'var(--accent-color)' }}>Answer</h3>
              <div className="prose" style={{ whiteSpace: 'pre-wrap' }}>
                {result.answer}
              </div>
            </div>
          )}

          {result.chunks?.length > 0 && (
            <div>
              <h3 style={{ marginBottom: '16px' }}>Retrieved Evidence ({result.chunks.length})</h3>
              {result.chunks.map((c: any, i: number) => (
                <EvidenceCard key={c.doc_id + c.chunk_index} chunk={c} index={i + 1} />
              ))}
            </div>
          )}
        </div>
      ) : (
        !loading && !error && (
          <EmptyState 
            icon={Search} 
            title="Search the Knowledge Base" 
            description="Enter a query above to retrieve relevant information from the company handbooks."
          />
        )
      )}
    </div>
  );
}
