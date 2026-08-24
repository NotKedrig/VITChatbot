import React, { useState } from 'react';
import { ChevronDown, ChevronUp, FileText } from 'lucide-react';

interface EvidenceCardProps {
  chunk: {
    title: string;
    doc_id: string;
    text: string;
    similarity_score: number;
    chunk_index: number;
  };
  index: number;
}

export default function EvidenceCard({ chunk, index }: EvidenceCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="glass-panel" style={{ padding: '16px', marginBottom: '12px' }}>
      <div 
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ 
            background: 'var(--accent-color)', 
            color: 'white', 
            borderRadius: '50%', 
            width: '24px', 
            height: '24px', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            fontSize: '12px',
            fontWeight: 'bold'
          }}>
            {index}
          </span>
          <FileText size={16} color="var(--text-secondary)" />
          <strong style={{ color: 'var(--text-primary)' }}>{chunk.title}</strong>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>(Chunk {chunk.chunk_index})</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Match: {(chunk.similarity_score * 100).toFixed(1)}%
          </span>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>
      
      {expanded && (
        <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-glass)' }}>
          <div className="prose" style={{ fontSize: '14px', background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '8px', whiteSpace: 'pre-wrap' }}>
            {chunk.text}
          </div>
        </div>
      )}
    </div>
  );
}
