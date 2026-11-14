import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { User, Project, Journal, ConversionJob, TransformationJob, ComplianceReport, ActivityItem, getAvatarInitials, DEFAULT_USER_PLAN } from '../types';
import { mockJournals as initialJournals, mockConversionHistory as initialConversions, mockTransformationHistory as initialTransformations, mockComplianceReport as initialReport } from '../data/mockData';
import {
  getMe,
  clearStoredToken,
  getStoredToken,
  listProjects,
  getProjectById,
  createProject as apiCreateProject,
  getProjectShortlist,
  shortlistJournal,
  unshortlistJournal,
} from '../lib/api';

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
  toggleShortlistJournal: (journalId: string, journalMeta?: Journal) => Promise<void>;
  setJournalShortlisted: (journalId: string, isShortlisted: boolean, journalMeta?: Journal) => void;
  selectedCompareJournalIds: string[];
  setSelectedCompareJournalIds: (ids: string[]) => void;
  toggleCompareJournal: (journalId: string) => void;
  compareNotification: string | null;
  clearCompareNotification: () => void;
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

  const [journals, setJournals] = useState<Journal[]>(() =>
    initialJournals.map(j => ({ ...j, isShortlisted: false }))
  );
  const [selectedCompareJournalIds, setSelectedCompareJournalIdsState] = useState<string[]>([]);
  const [compareNotification, setCompareNotification] = useState<string | null>(null);
  const [conversions, setConversions] = useState<ConversionJob[]>(initialConversions);
  const [transformations, setTransformations] = useState<TransformationJob[]>(initialTransformations);
  const [complianceReport] = useState<ComplianceReport>(initialReport);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const inFlightShortlistRef = useRef<Set<string>>(new Set());
  const creatingDefaultProjectRef = useRef<Promise<Project> | null>(null);

  const toggleSidebar = () => {
    setIsSidebarCollapsed(prev => !prev);
  };

  const addActivity = useCallback((title: string, subtitle: string, type: ActivityItem['type']) => {
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
  }, []);

  const setActiveProjectId = useCallback((id: string) => {
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
  }, []);

  const activeProject = activeProjectId ? projects.find(p => p.id === activeProjectId) : undefined;

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

      // Validate stored active project or default to the first project
      const storedId = localStorage.getItem(ACTIVE_PROJECT_KEY);
      if (storedId) {
        const found = res.items.find(p => p.id === storedId);
        if (found) {
          setActiveProjectIdState(storedId);
        } else {
          // If stored ID not in list, verify or fallback
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
      } else {
        setActiveProjectIdState('');
      }
    } catch (err: any) {
      setProjectsError(err.message || 'Failed to load projects');
    } finally {
      setIsProjectsLoading(false);
    }
  }, [setActiveProjectId]);

  useEffect(() => {
    let cancelled = false;
    const token = getStoredToken();
    if (!token || !activeProjectId || !/^\d+$/.test(activeProjectId)) {
      setJournals(prev => prev.map(j => (j.isShortlisted ? { ...j, isShortlisted: false } : j)));
      return;
    }

    getProjectShortlist(activeProjectId)
      .then((items) => {
        if (cancelled) return;
        const shortlistedMap = new Map<string, Journal>();
        for (const item of items) {
          shortlistedMap.set(item.id, { ...item, isShortlisted: true });
        }
        setJournals(prev => {
          const seenIds = new Set<string>();
          const updated = prev.map(j => {
            seenIds.add(j.id);
            const fromServer = shortlistedMap.get(j.id);
            if (fromServer) {
              return { ...j, ...fromServer, isShortlisted: true };
            }
            return j.isShortlisted ? { ...j, isShortlisted: false } : j;
          });
          for (const [id, item] of shortlistedMap.entries()) {
            if (!seenIds.has(id)) {
              updated.push(item);
            }
          }
          return updated;
        });
      })
      .catch(() => {
        // Ignore shortlist load failures during auth/project transitions
      });

    return () => {
      cancelled = true;
    };
  }, [activeProjectId]);

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

  const mergeJournals = useCallback((incoming: Journal[]) => {
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
          isShortlisted: Boolean(j.isShortlisted || existing?.isShortlisted),
        });
      }
      return Array.from(map.values());
    });
  }, []);

  const setJournalShortlisted = useCallback((journalId: string, isShortlisted: boolean, journalMeta?: Journal) => {
    setJournals(prev => {
      const exists = prev.some(j => j.id === journalId);
      if (exists) {
        return prev.map(j => (j.id === journalId ? { ...j, ...journalMeta, isShortlisted } : j));
      }
      if (journalMeta) {
        return [...prev, { ...journalMeta, isShortlisted }];
      }
      return prev;
    });
  }, []);

  const toggleShortlistJournal = useCallback(async (journalId: string, journalMeta?: Journal) => {
    if (inFlightShortlistRef.current.has(journalId)) {
      return;
    }

    const existing = journals.find(j => j.id === journalId) || journalMeta;
    const isCurrentlyShortlisted = Boolean(existing?.isShortlisted);
    const newState = !isCurrentlyShortlisted;

    inFlightShortlistRef.current.add(journalId);
    setJournalShortlisted(journalId, newState, journalMeta);

    try {
      let targetProjectId = activeProjectId && /^\d+$/.test(activeProjectId) ? activeProjectId : '';
      let shouldActivateProjectId = '';

      if (!targetProjectId) {
        const dbProject = projects.find(p => /^\d+$/.test(p.id));
        if (dbProject) {
          targetProjectId = dbProject.id;
          shouldActivateProjectId = dbProject.id;
        } else {
          if (!creatingDefaultProjectRef.current) {
            const researchField =
              journalMeta?.subjectCategory || existing?.subjectCategory || 'General Research';
            creatingDefaultProjectRef.current = apiCreateProject({
              title: 'My Research Workspace',
              researchField,
              field: researchField,
              abstract: '',
            });
          }
          const created = await creatingDefaultProjectRef.current;
          creatingDefaultProjectRef.current = null;
          setProjects(prev => (prev.some(p => p.id === created.id) ? prev : [created, ...prev]));
          targetProjectId = created.id;
          shouldActivateProjectId = created.id;
        }
      }

      if (newState) {
        await shortlistJournal(
          targetProjectId,
          journalId,
          journalMeta?.rawSimilarity ?? existing?.rawSimilarity ?? undefined
        );
        addActivity(
          'Journal shortlisted',
          existing?.title || journalMeta?.title || `Journal #${journalId}`,
          'journal'
        );
      } else {
        await unshortlistJournal(targetProjectId, journalId);
      }

      if (shouldActivateProjectId) {
        setActiveProjectId(shouldActivateProjectId);
      }
      await refreshProjects();
    } catch (err) {
      creatingDefaultProjectRef.current = null;
      setJournalShortlisted(journalId, isCurrentlyShortlisted, journalMeta);
      console.error('Failed to toggle shortlist status:', err);
    } finally {
      inFlightShortlistRef.current.delete(journalId);
    }
  }, [activeProjectId, projects, journals, setJournalShortlisted, setActiveProjectId, addActivity, refreshProjects]);

  const setSelectedCompareJournalIds = useCallback((ids: string[]) => {
    const deduped = Array.from(new Set(ids.map((id) => String(id).trim()).filter(Boolean))).slice(0, 4);
    setSelectedCompareJournalIdsState(deduped);
  }, []);

  const clearCompareNotification = useCallback(() => {
    setCompareNotification(null);
  }, []);

  const toggleCompareJournal = useCallback((journalId: string) => {
    if (selectedCompareJournalIds.includes(journalId)) {
      setCompareNotification(null);
      setSelectedCompareJournalIdsState(prev => prev.filter(id => id !== journalId));
      return;
    }
    if (selectedCompareJournalIds.length >= 4) {
      setCompareNotification('At most four journals can be compared at one time.');
      return;
    }
    setCompareNotification(null);
    setSelectedCompareJournalIdsState(prev => (prev.includes(journalId) || prev.length >= 4 ? prev : [...prev, journalId]));
  }, [selectedCompareJournalIds]);

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

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setUserState(null);
      setProjects([]);
      setActiveProjectIdState('');
      setSelectedCompareJournalIdsState([]);
      setCompareNotification(null);
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
        setSelectedCompareJournalIdsState([]);
        setCompareNotification(null);
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
      setSelectedCompareJournalIdsState([]);
      setCompareNotification(null);
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
    setSelectedCompareJournalIdsState([]);
    setCompareNotification(null);
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
        setSelectedCompareJournalIds,
        toggleCompareJournal,
        compareNotification,
        clearCompareNotification,
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
