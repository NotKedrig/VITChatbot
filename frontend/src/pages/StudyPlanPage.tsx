import React, { useState } from 'react';
import { GraduationCap } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { apiFetch } from '../lib/api';
import { STUDENT_ID } from '../lib/constants';
import PlanGeneratorForm from '../components/PlanGeneratorForm';
import StudyPlanView from '../components/StudyPlanView';
import EmptyState from '../components/EmptyState';

export default function StudyPlanPage() {
  const { data, loading, refetch } = useApi<any>(() => apiFetch(`/api/plan/${STUDENT_ID}`));
  const [generating, setGenerating] = useState(false);

  const handleGenerate = async (companies: string[], time: string, skills: string, msg: string) => {
    setGenerating(true);
    try {
      await apiFetch('/api/plan/generate', {
        method: 'POST',
        body: JSON.stringify({
          student_id: STUDENT_ID,
          target_companies: companies,
          available_time: time,
          skills: skills,
          message: msg
        })
      });
      await refetch();
    } catch (err) {
      console.error(err);
      alert("Failed to generate plan");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <div className="page-container"><div className="spinner" /></div>;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Study Plan</h1>
        <p className="page-description">Generate or review your adaptive study plan.</p>
      </div>

      <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div style={{ flex: '1 1 350px' }}>
          <PlanGeneratorForm onSubmit={handleGenerate} loading={generating} />
        </div>
        
        <div style={{ flex: '2 1 500px' }}>
          {data?.plan ? (
            <StudyPlanView plan={data.plan} revisions={data.revisions} />
          ) : (
            <EmptyState 
              icon={GraduationCap}
              title="No active study plan"
              description="Fill out the form to generate a customized study plan based on your target companies and available time."
            />
          )}
        </div>
      </div>
    </div>
  );
}
