import React, { useState, useEffect } from 'react';
import { Bot, User, Bell, LayoutDashboard, MessageSquare } from 'lucide-react';
import ChatPanel from './components/ChatPanel';
import DashboardPanel from './components/DashboardPanel';
import StudyPlanView from './components/StudyPlanView';
import './index.css';

const STUDENT_ID = "demo_student";
const THREAD_ID = "demo_thread_" + Math.floor(Math.random() * 1000);

export default function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'plan'>('chat');
  const [state, setState] = useState<any>(null);
  const [currentPlan, setCurrentPlan] = useState<any>(null);

  // Poll state occasionally or on load
  const fetchState = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/state/${STUDENT_ID}`);
      if (res.ok) {
        const data = await res.json();
        setState(data);
      }
    } catch (e) {
      console.error("Failed to fetch state", e);
    }
  };

  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-container">
      {/* Sidebar / Dashboard */}
      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '24px', borderBottom: '1px solid var(--border-glass)' }}>
          <h2 className="text-gradient" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bot size={28} color="var(--accent-color)" />
            VITian POC
          </h2>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <DashboardPanel state={state} />
        </div>
      </div>

      {/* Main Content Area */}
      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Top Nav */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-glass)', display: 'flex', gap: '16px' }}>
          <button 
            className={`glass-button ${activeTab === 'chat' ? 'primary' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            <MessageSquare size={18} /> Chat
          </button>
          <button 
            className={`glass-button ${activeTab === 'plan' ? 'primary' : ''}`}
            onClick={() => setActiveTab('plan')}
          >
            <LayoutDashboard size={18} /> Study Plan
            {currentPlan && <span style={{ width: 8, height: 8, background: 'var(--success)', borderRadius: '50%' }} />}
          </button>
        </div>

        {/* Content View */}
        <div style={{ flex: 1, position: 'relative' }}>
          {activeTab === 'chat' ? (
            <ChatPanel 
              studentId={STUDENT_ID} 
              threadId={THREAD_ID} 
              onPlanUpdate={(plan) => {
                if (plan) setCurrentPlan(plan);
                fetchState(); // Refresh dashboard on new msgs
              }} 
            />
          ) : (
            <StudyPlanView plan={currentPlan} />
          )}
        </div>
      </div>
    </div>
  );
}
