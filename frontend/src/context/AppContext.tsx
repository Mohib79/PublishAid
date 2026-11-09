import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, Project, Journal, ConversionJob, TransformationJob, ComplianceReport, ActivityItem, getAvatarInitials, DEFAULT_USER_PLAN } from '../types';
import { mockJournals as initialJournals, mockConversionHistory as initialConversions, mockTransformationHistory as initialTransformations, mockComplianceReport as initialReport } from '../data/mockData';
import { getMe, clearStoredToken, getStoredToken, listProjects, getProjectById, createProject as apiCreateProject } from '../lib/api';

const ACTIVE_PROJECT_KEY = 'publishaid_active_project_id';

interface AppContextType {
  user: User | null;
  setUser: (user: User | null) => void;
  isAuthLoading: boolean;
  isSidebarCollapsed: boolean;
  toggleSidebar: () => void;
  projects: Project[];
  isProjectsLoading: boolean;
  projectsError: string | null;
  refreshProjects: () => Promise<void>;
  activeProjectId: string;
  setActiveProjectId: (id: string) => void;
  activeProject: Project | undefined;
  setActiveProject: (project: Project) => void;
  addProject: (title: string, field: string, abstract?: string) => Promise<Project>;
  journals: Journal[];
  mergeJournals: (incoming: Journal[]) => void;
  toggleShortlistJournal: (journalId: string) => void;
  setJournalShortlisted: (journalId: string, isShortlisted: boolean) => void;
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

  const [projects, setProjects] = useState<Project[]>([]);
  const [isProjectsLoading, setIsProjectsLoading] = useState<boolean>(false);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [activeProjectId, setActiveProjectIdState] = useState<string>(() => {
    try {
      return localStorage.getItem(ACTIVE_PROJECT_KEY) || '';
    } catch {
      return '';
    }
  });

  const [journals, setJournals] = useState<Journal[]>(initialJournals);
  const [selectedCompareJournalIds, setSelectedCompareJournalIds] = useState<string[]>(['jrn_01', 'jrn_02', 'jrn_03']);
  const [conversions, setConversions] = useState<ConversionJob[]>(initialConversions);
  const [transformations, setTransformations] = useState<TransformationJob[]>(initialTransformations);
  const [complianceReport] = useState<ComplianceReport>(initialReport);
  const [activities, setActivities] = useState<ActivityItem[]>([]);

  const toggleSidebar = () => {
    setIsSidebarCollapsed(prev => !prev);
  };

  const setActiveProjectId = (id: string) => {
    setActiveProjectIdState(id);
    try {
      if (id) {
        localStorage.setItem(ACTIVE_PROJECT_KEY, id);
      } else {
        localStorage.removeItem(ACTIVE_PROJECT_KEY);
      }
    } catch {
      // Ignore storage errors
    }
  };

  const activeProject = projects.find(p => p.id === activeProjectId) || projects[0];

  const setActiveProject = (project: Project) => {
    setProjects(prev => {
      const exists = prev.some(p => p.id === project.id);
      return exists ? prev.map(p => p.id === project.id ? project : p) : [project, ...prev];
    });
    setActiveProjectId(project.id);
  };

  const refreshProjects = useCallback(async () => {
    if (!getStoredToken()) {
      setProjects([]);
      return;
    }
    setIsProjectsLoading(true);
    setProjectsError(null);
    try {
      const res = await listProjects({ pageSize: 100 });
      setProjects(res.items || []);

      // Validate stored active project
      const storedId = localStorage.getItem(ACTIVE_PROJECT_KEY);
      if (storedId) {
        const found = res.items.find(p => p.id === storedId);
        if (found) {
          setActiveProjectIdState(storedId);
        } else {
          // If stored ID not in list, verify or silently clear
          try {
            const fetched = await getProjectById(storedId);
            setActiveProjectIdState(fetched.id);
          } catch {
            localStorage.removeItem(ACTIVE_PROJECT_KEY);
            if (res.items.length > 0) {
              setActiveProjectId(res.items[0].id);
            } else {
              setActiveProjectIdState('');
            }
          }
        }
      } else if (res.items.length > 0) {
        setActiveProjectId(res.items[0].id);
      }
    } catch (err: any) {
      setProjectsError(err.message || 'Failed to load projects');
    } finally {
      setIsProjectsLoading(false);
    }
  }, []);

  const addProject = async (title: string, field: string, abstract = ''): Promise<Project> => {
    const created = await apiCreateProject({
      title,
      researchField: field,
      field,
      abstract,
    });
    setProjects(prev => [created, ...prev]);
    setActiveProjectId(created.id);
    addActivity('Project created', title, 'project');
    return created;
  };

  const mergeJournals = (incoming: Journal[]) => {
    setJournals(prev => {
      const map = new Map<string, Journal>();
      for (const j of prev) {
        map.set(j.id, j);
      }
      for (const j of incoming) {
        const existing = map.get(j.id);
        map.set(j.id, {
          ...(existing || {}),
          ...j,
          // Preserve shortlist status if already true
          isShortlisted: j.isShortlisted ?? existing?.isShortlisted ?? false,
        });
      }
      return Array.from(map.values());
    });
  };

  const setJournalShortlisted = (journalId: string, isShortlisted: boolean) => {
    setJournals(prev =>
      prev.map(j => {
        if (j.id === journalId) {
          return { ...j, isShortlisted };
        }
        return j;
      })
    );
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
      setProjects([]);
      setActiveProjectIdState('');
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
        refreshProjects();
      })
      .catch(() => {
        clearStoredToken();
        setUserState(null);
        setProjects([]);
        setActiveProjectIdState('');
      })
      .finally(() => {
        setIsAuthLoading(false);
      });
  }, [refreshProjects]);

  const setUser = (newUser: User | null) => {
    if (newUser) {
      setUserState({
        ...newUser,
        avatarInitials: newUser.avatarInitials || getAvatarInitials(newUser.fullName),
        plan: newUser.plan || DEFAULT_USER_PLAN,
        role: newUser.role || 'Researcher',
      });
      refreshProjects();
    } else {
      setUserState(null);
      setProjects([]);
      setActiveProjectIdState('');
    }
  };

  const logout = () => {
    clearStoredToken();
    try {
      localStorage.removeItem(ACTIVE_PROJECT_KEY);
    } catch {
      // Ignore
    }
    setUserState(null);
    setProjects([]);
    setActiveProjectIdState('');
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
        isProjectsLoading,
        projectsError,
        refreshProjects,
        activeProjectId,
        setActiveProjectId,
        activeProject,
        setActiveProject,
        addProject,
        journals,
        mergeJournals,
        toggleShortlistJournal,
        setJournalShortlisted,
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
