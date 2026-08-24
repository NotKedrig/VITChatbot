import React from 'react';
import { Link } from 'react-router-dom';

interface StatCardProps {
  title: string;
  value: React.ReactNode;
  icon?: React.ElementType;
  to?: string;
  className?: string;
}

export default function StatCard({ title, value, icon: Icon, to, className = "" }: StatCardProps) {
  const content = (
    <div className={`glass-panel stat-card ${className}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="stat-card-title">{title}</span>
        {Icon && <Icon size={20} color="var(--accent-color)" />}
      </div>
      <div className="stat-card-value text-gradient">{value}</div>
    </div>
  );

  return to ? <Link to={to} style={{ textDecoration: 'none' }}>{content}</Link> : content;
}
