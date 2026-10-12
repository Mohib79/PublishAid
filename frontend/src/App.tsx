import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { SignUpPage } from './pages/SignUpPage';
import { DashboardPage } from './pages/DashboardPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { BrowseJournalsPage } from './pages/BrowseJournalsPage';
import { JournalFinderPage } from './pages/JournalFinderPage';
import { JournalComparisonPage } from './pages/JournalComparisonPage';
import { GuidelinesTemplatesPage } from './pages/GuidelinesTemplatesPage';
import { ManuscriptTransformationPage } from './pages/ManuscriptTransformationPage';
import { DocumentConverterPage } from './pages/DocumentConverterPage';
import { PaperSummarizerPage } from './pages/PaperSummarizerPage';
import { ComplianceCheckerPage } from './pages/ComplianceCheckerPage';
import { SettingsPage } from './pages/SettingsPage';

export const App: React.FC = () => {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Auth Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignUpPage />} />

          {/* Main App Layout */}
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/browse" element={<BrowseJournalsPage />} />
            <Route path="/finder" element={<JournalFinderPage />} />
            <Route path="/compare" element={<JournalComparisonPage />} />
            <Route path="/guidelines" element={<GuidelinesTemplatesPage />} />
            <Route path="/transformation" element={<ManuscriptTransformationPage />} />
            <Route path="/converter" element={<DocumentConverterPage />} />
            <Route path="/summarizer" element={<PaperSummarizerPage />} />
            <Route path="/compliance" element={<ComplianceCheckerPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
};

export default App;
