import React from 'react';
import { NavLink } from 'react-router-dom';
import { Bot, LayoutDashboard, MessageSquare, Search, GraduationCap, TrendingUp, Bell, User } from 'lucide-react';
import SystemStatus from './SystemStatus';

export default function Sidebar() {
  const links = [
    { to: "/", icon: LayoutDashboard, label: "Dashboard" },
    { to: "/chat", icon: MessageSquare, label: "Chat" },
    { to: "/research", icon: Search, label: "Company Research" },
    { to: "/plan", icon: GraduationCap, label: "Study Plan" },
    { to: "/progress", icon: TrendingUp, label: "Progress" },
    { to: "/reminders", icon: Bell, label: "Reminders" },
    { to: "/profile", icon: User, label: "Profile" }
  ];

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2 className="text-gradient" style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}>
          <Bot size={24} color="var(--accent-color)" />
          VITian POC
        </h2>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, overflowY: 'auto' }}>
        {links.map(link => (
          <NavLink 
            key={link.to} 
            to={link.to} 
            className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}
            end={link.to === "/"}
          >
            <link.icon size={18} />
            <span>{link.label}</span>
          </NavLink>
        ))}
      </div>

      <div className="sidebar-footer">
        <SystemStatus />
      </div>
    </div>
  );
}
