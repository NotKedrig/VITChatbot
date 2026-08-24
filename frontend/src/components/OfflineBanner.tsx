import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function OfflineBanner() {
  return (
    <div className="banner warning">
      <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
      <div>
        <strong>Offline Knowledge-Base Mode</strong>
        <p style={{ marginTop: '4px', opacity: 0.9 }}>
          Showing retrieved evidence because the LLM is unavailable (API key missing or quota exhausted). 
          The following passages were retrieved from the local knowledge base but no synthesized answer could be generated.
        </p>
      </div>
    </div>
  );
}
