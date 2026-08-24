import React from 'react';
import { MessageSquare } from 'lucide-react';
import ChatPanel from '../components/ChatPanel';
import { STUDENT_ID, getThreadId } from '../lib/constants';

export default function ChatPage() {
  const threadId = getThreadId();

  return (
    <div className="page-container" style={{ padding: 0, display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '24px 48px', borderBottom: '1px solid var(--border-glass)', background: 'var(--bg-glass)' }}>
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <MessageSquare size={24} color="var(--accent-color)" /> Chat Assistant
        </h1>
        <p className="page-description">Ask questions, get career advice, and clarify concepts.</p>
      </div>
      
      <div style={{ flex: 1, position: 'relative' }}>
        <ChatPanel 
          studentId={STUDENT_ID} 
          threadId={threadId} 
          onPlanUpdate={() => {}} 
        />
      </div>
    </div>
  );
}
