import React from 'react';

interface EmptyStateProps {
  icon: React.ElementType;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export default function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <Icon size={48} />
      <h3 style={{ marginBottom: '8px', color: 'var(--text-primary)' }}>{title}</h3>
      <p style={{ marginBottom: '24px', maxWidth: '400px' }}>{description}</p>
      {action}
    </div>
  );
}
