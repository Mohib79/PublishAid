import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, Project, Journal, ConversionJob, TransformationJob, ComplianceReport, ActivityItem, getAvatarInitials, DEFAULT_USER_PLAN } from '../types';
import { mockProjects as initialProjects, mockJournals as initialJournals, mockConversionHistory as initialConversions, mockTransformationHistory as initialTransformations, mockComplianceReport as initialReport, mockRecentActivity as initialActivities } from '../data/mockData';
import { getMe, clearStoredToken, getStoredToken } from '../lib/api';

interface AppContextType {
  user: User | null;
  setUser: (user: User | null) => void;
  isAuthLoading: boolean;
  isSidebarCollapsed: boolean;
  toggleSidebar: () => void;
  projects: Project[];
  activeProjectId: string;
  setActiveProjectId: (id: string) => void;
  activeProject: Project | undefined;
  addProject: (title: string, field: string, abstract?: string) => Project;
  journals: Journal[];
  toggleShortlistJournal: (journalId: string) => void;
  selectedCompareJournalIds: string[];
  toggleCompareJournal: (journalId: string) => void;
  conversions: ConversionJob[];
  addConversion: (file: File | { name: string; size: string }, sourceFormat: 'DOCX' | 'TEX', targetFormat: 'TEX' | 'DOCX') => ConversionJob;
  transformations: TransformationJob[];
  addTransformation: (manuscriptName: string, targetJournal: string) => TransformationJob;
  complianceReport: ComplianceReport;
  activities: ActivityItem[];
  addActivity: (title: string, subtitle: string, type: ActivityItem['type']) => void;
  logout: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUserState] = useState<User | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState<boolean>(true);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [projects, setProjects] = useState<Project[]>(initialProjects);
  const [activeProjectId, setActiveProjectId] = useState<string>('proj_01');
  const [journals, setJournals] = useState<Journal[]>(initialJournals);
  const [selectedCompareJournalIds, setSelectedCompareJournalIds] = useState<string[]>(['jrn_01', 'jrn_02', 'jrn_03']);
  const [conversions, setConversions] = useState<ConversionJob[]>(initialConversions);
  const [transformations, setTransformations] = useState<TransformationJob[]>(initialTransformations);
  const [complianceReport] = useState<ComplianceReport>(initialReport);
  const [activities, setActivities] = useState<ActivityItem[]>(initialActivities);

  const toggleSidebar = () => {
    setIsSidebarCollapsed(prev => !prev);
  };

  const activeProject = projects.find(p => p.id === activeProjectId) || projects[0];

  const addProject = (title: string, field: string, abstract = '') => {
    const newProj: Project = {
      id: `proj_${Date.now()}`,
      title,
      field,
      abstract,
      keywords: [],
      status: 'Draft',
      updatedAt: 'Just now',
      wordCount: 0,
    };
    setProjects(prev => [newProj, ...prev]);
    setActiveProjectId(newProj.id);
    addActivity('Project created', title, 'project');
    return newProj;
  };

  const toggleShortlistJournal = (journalId: string) => {
    setJournals(prev =>
      prev.map(j => {
        if (j.id === journalId) {
          const newState = !j.isShortlisted;
          if (newState) {
            addActivity('Journal shortlisted', j.title, 'journal');
          }
          return { ...j, isShortlisted: newState };
        }
        return j;
      })
    );
  };

  const toggleCompareJournal = (journalId: string) => {
    setSelectedCompareJournalIds(prev => {
      if (prev.includes(journalId)) {
        return prev.filter(id => id !== journalId);
      }
      if (prev.length >= 4) {
        alert('At most 4 journals can be compared simultaneously.');
        return prev;
      }
      return [...prev, journalId];
    });
  };

  const addConversion = (file: File | { name: string; size: string }, sourceFormat: 'DOCX' | 'TEX', targetFormat: 'TEX' | 'DOCX') => {
    const sizeStr = 'size' in file && typeof file.size === 'number' ? `${(file.size / (1024 * 1024)).toFixed(1)} MB` : (file as any).size || '2.0 MB';
    const newJob: ConversionJob = {
      id: `conv_${Date.now()}`,
      fileName: file.name,
      fileSize: sizeStr,
      sourceFormat,
      targetFormat,
      date: 'Just now',
      status: 'Completed',
    };
    setConversions(prev => [newJob, ...prev]);
    addActivity('Conversion completed', file.name, 'conversion');
    return newJob;
  };

  const addTransformation = (manuscriptName: string, targetJournal: string) => {
    const newJob: TransformationJob = {
      id: `tr_${Date.now()}`,
      manuscriptName,
      fileSize: '2.4 MB',
      targetJournal,
      date: 'Just now',
      status: 'Completed',
      changesApplied: {
        singleToDoubleColumn: true,
        citationStyle: 'APA',
        marginsUpdated: true,
        manualReviewItemsCount: 2,
      },
    };
    setTransformations(prev => [newJob, ...prev]);
    addActivity('Manuscript adapted', `${manuscriptName} -> ${targetJournal}`, 'conversion');
    return newJob;
  };

  const addActivity = (title: string, subtitle: string, type: ActivityItem['type']) => {
    setActivities(prev => [
      {
        id: `act_${Date.now()}`,
        title,
        subtitle,
        timestamp: 'Just now',
        type,
      },
      ...prev,
    ]);
  };

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setUserState(null);
      setIsAuthLoading(false);
      return;
    }

    getMe()
      .then((userData) => {
        setUserState({
          ...userData,
          avatarInitials: userData.avatarInitials || getAvatarInitials(userData.fullName),
          plan: userData.plan || DEFAULT_USER_PLAN,
          role: userData.role || 'Researcher',
        });
      })
      .catch(() => {
        clearStoredToken();
        setUserState(null);
      })
      .finally(() => {
        setIsAuthLoading(false);
      });
  }, []);

  const setUser = (newUser: User | null) => {
    if (newUser) {
      setUserState({
        ...newUser,
        avatarInitials: newUser.avatarInitials || getAvatarInitials(newUser.fullName),
        plan: newUser.plan || DEFAULT_USER_PLAN,
        role: newUser.role || 'Researcher',
      });
    } else {
      setUserState(null);
    }
  };

  const logout = () => {
    clearStoredToken();
    setUserState(null);
  };

  return (
    <AppContext.Provider
      value={{
        user,
        setUser,
        isAuthLoading,
        isSidebarCollapsed,
        toggleSidebar,
        projects,
        activeProjectId,
        setActiveProjectId,
        activeProject,
        addProject,
        journals,
        toggleShortlistJournal,
        selectedCompareJournalIds,
        toggleCompareJournal,
        conversions,
        addConversion,
        transformations,
        addTransformation,
        complianceReport,
        activities,
        addActivity,
        logout,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
