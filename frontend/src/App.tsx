import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import DashboardPage from './pages/DashboardPage';
import ChatPage from './pages/ChatPage';
import CompanyResearchPage from './pages/CompanyResearchPage';
import StudyPlanPage from './pages/StudyPlanPage';
import ProgressPage from './pages/ProgressPage';
import RemindersPage from './pages/RemindersPage';
import ProfilePage from './pages/ProfilePage';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="research" element={<CompanyResearchPage />} />
          <Route path="plan" element={<StudyPlanPage />} />
          <Route path="progress" element={<ProgressPage />} />
          <Route path="reminders" element={<RemindersPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
