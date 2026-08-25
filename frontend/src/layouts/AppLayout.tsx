import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import NotificationPoller from '../components/NotificationPoller';

export default function AppLayout() {
  return (
    <div className="app-layout">
      <NotificationPoller />
      <Sidebar />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
