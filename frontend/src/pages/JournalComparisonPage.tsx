import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Plus,
  X,
  Check,
  Bookmark,
  Info,
  CheckCircle2,
  Columns2,
  Download,
  AlertCircle,
  Search,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  FolderPlus,
  Loader2,
  SlidersHorizontal,
  ArrowRight,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/StatusBadge';
import {
  ApiError,
  browseJournals,
  compareJournals,
  getJournalById,
  getProjectShortlist,
  setTargetJournal,
} from '../lib/api';
import {
  CompareJournalHeader,
  CompareRow,
  Journal,
  JournalCompareResponse,
} from '../types';

const CSV_FORMULA_TRIGGER_RE = /^[=+\-@\t\r]/;

export function escapeCsvCell(raw: unknown): string {
  let str = raw === null || raw === undefined ? 'N/A' : String(raw);
  if (CSV_FORMULA_TRIGGER_RE.test(str)) {
    str = `'${str}`;
  }
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function formatCellValueForCsv(row: CompareRow, value: unknown): string {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  if (Array.isArray(value)) {
    return value.join('; ');
  }
  if (typeof value === 'number') {
    if (row.key === 'citeScore' || row.key === 'impactFactor' || row.key === 'acceptanceRate') {
      return value.toFixed(1);
    }
    if (row.key === 'sjr' || row.key === 'citedness2yr') {
      return value.toFixed(2);
    }
    return String(value);
  }
  return String(value);
}

function formatReviewWeeks(val: number): string {
  const numStr = Number(val.toFixed(1)).toString();
  return numStr === '1' ? '1 week' : `${numStr} weeks`;
}

function formatUpdatedDate(iso?: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return null;
  }
}

export const JournalComparisonPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    journals: contextJournals,
    projects,
    activeProject,
    setActiveProjectId,
    addProject,
    refreshProjects,
    selectedCompareJournalIds,
    setSelectedCompareJournalIds,
    addActivity,
  } = useApp();

  // Parse IDs from URL (?ids=...)
  const rawIdsParam = searchParams.get('ids');

  const urlParsed = useMemo(() => {
    if (!rawIdsParam) {
      return { ids: [] as string[], overflowed: false };
    }
    const tokens = rawIdsParam
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
    const deduped = Array.from(new Set(tokens));
    return {
      ids: deduped.slice(0, 4),
      overflowed: deduped.length > 4,
    };
  }, [rawIdsParam]);

  const didInitFromShortlistRef = useRef(false);

  // Redirect /compare (without ?ids=) to /compare?ids=... if context already has >= 2 selected,
  // or fall back on initial mount to the active workspace's shortlisted DB journal IDs.
  useEffect(() => {
    if (rawIdsParam !== null) {
      didInitFromShortlistRef.current = true;
      return;
    }
    if (selectedCompareJournalIds.length >= 2) {
      didInitFromShortlistRef.current = true;
      setSearchParams({ ids: selectedCompareJournalIds.join(',') }, { replace: true });
      return;
    }
    if (!didInitFromShortlistRef.current) {
      const shortlistedIds = contextJournals
        .filter((j) => j.isShortlisted && /^\d+$/.test(j.id))
        .map((j) => j.id);
      if (shortlistedIds.length > 0) {
        didInitFromShortlistRef.current = true;
        setSearchParams({ ids: shortlistedIds.slice(0, 4).join(',') }, { replace: true });
      }
    }
  }, [rawIdsParam, selectedCompareJournalIds, contextJournals, setSearchParams]);

  // Effective journal IDs shown on this page
  const activeIds = useMemo(() => {
    if (rawIdsParam !== null) {
      return urlParsed.ids;
    }
    return selectedCompareJournalIds;
  }, [rawIdsParam, urlParsed.ids, selectedCompareJournalIds]);

  // Keep context selection synchronized with URL IDs when URL changes
  useEffect(() => {
    if (rawIdsParam !== null) {
      setSelectedCompareJournalIds(urlParsed.ids);
    }
  }, [rawIdsParam, urlParsed.ids, setSelectedCompareJournalIds]);

  const [bannerAlert, setBannerAlert] = useState<{
    type: 'info' | 'warning' | 'error' | 'success';
    message: string;
  } | null>(null);

  useEffect(() => {
    if (urlParsed.overflowed) {
      setBannerAlert({
        type: 'warning',
        message: 'At most four journals can be compared at one time. Showing the first four selected journals.',
      });
    }
  }, [urlParsed.overflowed]);

  // Controls state
  const [onlyDifferences, setOnlyDifferences] = useState(false);
  const [includeRequirements, setIncludeRequirements] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [expandedScopes, setExpandedScopes] = useState<Record<string, boolean>>({});
  const [showNotes, setShowNotes] = useState(false);

  // Comparison fetch state
  const [compareData, setCompareData] = useState<JournalCompareResponse | null>(null);
  const [isLoadingCompare, setIsLoadingCompare] = useState(false);
  const [singleChipLabelMap, setSingleChipLabelMap] = useState<Record<string, string>>({});

  // Determine real numeric DB projectId
  const activeDbProjectId = useMemo(() => {
    return activeProject?.id && /^\d+$/.test(activeProject.id) ? activeProject.id : null;
  }, [activeProject]);

  // Add Journal Picker modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [pickerTab, setPickerTab] = useState<'shortlist' | 'catalog'>('catalog');
  const [shortlistItems, setShortlistItems] = useState<Journal[]>([]);
  const [isLoadingShortlist, setIsLoadingShortlist] = useState(false);
  const [catalogSearch, setCatalogSearch] = useState('');
  const [debouncedCatalogSearch, setDebouncedCatalogSearch] = useState('');
  const [catalogItems, setCatalogItems] = useState<Journal[]>([]);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(false);

  // Target journal assignment & project chooser modal state
  const [isSettingTargetId, setIsSettingTargetId] = useState<string | null>(null);
  const [pendingTargetJournal, setPendingTargetJournal] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const [newProjectTitle, setNewProjectTitle] = useState('');
  const [newProjectField, setNewProjectField] = useState('Computer science');
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [chooserError, setChooserError] = useState<string | null>(null);

  const updateUrlIds = useCallback(
    (nextIds: string[]) => {
      const cleaned = Array.from(new Set(nextIds.map((id) => id.trim()).filter(Boolean))).slice(0, 4);
      setSelectedCompareJournalIds(cleaned);
      if (cleaned.length === 0) {
        setSearchParams({}, { replace: true });
      } else {
        setSearchParams({ ids: cleaned.join(',') }, { replace: true });
      }
    },
    [setSearchParams, setSelectedCompareJournalIds]
  );

  // Fetch metadata label for single journal chip when < 2 IDs
  useEffect(() => {
    if (activeIds.length !== 1) return;
    const jid = activeIds[0];
    if (singleChipLabelMap[jid]) return;
    const fromCtx = contextJournals.find((j) => j.id === jid);
    if (fromCtx) {
      setSingleChipLabelMap((prev) => ({ ...prev, [jid]: fromCtx.title }));
      return;
    }
    if (/^\d+$/.test(jid)) {
      getJournalById(jid)
        .then((j) => {
          setSingleChipLabelMap((prev) => ({ ...prev, [jid]: j.title }));
        })
        .catch(() => {
          // Ignore lookup error for single placeholder chip
        });
    }
  }, [activeIds, contextJournals, singleChipLabelMap]);

  // Fetch comparison data from server when 2..4 IDs are active
  const fetchComparison = useCallback(async () => {
    if (activeIds.length < 2) {
      setCompareData(null);
      return;
    }

    setIsLoadingCompare(true);
    try {
      const data = await compareJournals(activeIds, activeDbProjectId, includeRequirements);
      setCompareData(data);
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === 404 && Array.isArray(apiErr.missingIds) && apiErr.missingIds.length > 0) {
        const missingSet = new Set(apiErr.missingIds.map(String));
        const remaining = activeIds.filter((id) => !missingSet.has(String(id)));
        setBannerAlert({
          type: 'warning',
          message: `Removed unavailable journal ID(s): ${apiErr.missingIds.join(', ')}.`,
        });
        setCompareData(null);
        updateUrlIds(remaining);
      } else {
        setBannerAlert({
          type: 'error',
          message: apiErr.message || 'Unable to load journal comparison.',
        });
        setCompareData(null);
      }
    } finally {
      setIsLoadingCompare(false);
    }
  }, [activeIds, activeDbProjectId, includeRequirements, updateUrlIds]);

  useEffect(() => {
    fetchComparison();
  }, [fetchComparison]);

  // Debounce catalog search inside picker modal
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedCatalogSearch(catalogSearch);
    }, 250);
    return () => clearTimeout(timer);
  }, [catalogSearch]);

  // Load shortlist items when picker opens
  useEffect(() => {
    if (!isAddModalOpen) return;
    if (activeDbProjectId) {
      setIsLoadingShortlist(true);
      getProjectShortlist(activeDbProjectId)
        .then((items) => setShortlistItems(items))
        .catch(() => setShortlistItems([]))
        .finally(() => setIsLoadingShortlist(false));
    } else {
      setShortlistItems([]);
    }
  }, [isAddModalOpen, activeDbProjectId]);

  // Load catalog search results when picker opens or search changes
  useEffect(() => {
    if (!isAddModalOpen) return;
    setIsLoadingCatalog(true);
    browseJournals({ search: debouncedCatalogSearch, limit: 20, sortBy: 'title', sortOrder: 'asc' })
      .then((res) => setCatalogItems(res.items || []))
      .catch(() => setCatalogItems([]))
      .finally(() => setIsLoadingCatalog(false));
  }, [isAddModalOpen, debouncedCatalogSearch]);

  const handleRemoveJournal = (idToRemove: string) => {
    setBannerAlert(null);
    updateUrlIds(activeIds.filter((id) => id !== idToRemove));
  };

  const handleAddJournal = (journal: Journal) => {
    if (activeIds.includes(journal.id)) return;
    if (activeIds.length >= 4) {
      setBannerAlert({
        type: 'warning',
        message: 'At most four journals can be compared at one time.',
      });
      return;
    }
    setBannerAlert(null);
    setSingleChipLabelMap((prev) => ({ ...prev, [journal.id]: journal.title }));
    updateUrlIds([...activeIds, journal.id]);
  };

  const assignPrimaryTarget = async (
    projectId: string,
    projectTitle: string,
    journalId: string,
    journalTitle: string
  ) => {
    setIsSettingTargetId(journalId);
    try {
      await setTargetJournal(projectId, journalId);
      addActivity('Target journal assigned', journalTitle, 'journal');
      await refreshProjects();
      await fetchComparison();
      setBannerAlert({
        type: 'success',
        message: `"${journalTitle}" has been set as the primary target journal for "${projectTitle}".`,
      });
      setPendingTargetJournal(null);
    } catch (err: any) {
      setBannerAlert({
        type: 'error',
        message: err?.message || 'Failed to assign primary target journal.',
      });
    } finally {
      setIsSettingTargetId(null);
    }
  };

  const handleSetTargetClick = async (journalHeader: CompareJournalHeader) => {
    if (activeDbProjectId && activeProject) {
      await assignPrimaryTarget(
        activeDbProjectId,
        activeProject.title,
        journalHeader.id,
        journalHeader.title
      );
      return;
    }
    setChooserError(null);
    setPendingTargetJournal({ id: journalHeader.id, title: journalHeader.title });
  };

  const handleSelectExistingProject = async (projectId: string, projectTitle: string) => {
    if (!pendingTargetJournal) return;
    setActiveProjectId(projectId);
    await assignPrimaryTarget(
      projectId,
      projectTitle,
      pendingTargetJournal.id,
      pendingTargetJournal.title
    );
  };

  const handleCreateAndAssignProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pendingTargetJournal) return;
    const cleanTitle = newProjectTitle.trim();
    if (!cleanTitle) {
      setChooserError('Please enter a project title.');
      return;
    }
    setChooserError(null);
    setIsCreatingProject(true);
    try {
      const created = await addProject(cleanTitle, newProjectField.trim() || 'Computer science', '');
      setNewProjectTitle('');
      await assignPrimaryTarget(
        created.id,
        created.title,
        pendingTargetJournal.id,
        pendingTargetJournal.title
      );
    } catch (err: any) {
      setChooserError(err?.message || 'Failed to create project.');
    } finally {
      setIsCreatingProject(false);
    }
  };

  const toggleGroupCollapsed = (groupKey: string) => {
    setCollapsedGroups((prev) => ({ ...prev, [groupKey]: !prev[groupKey] }));
  };

  const toggleScopeExpanded = (journalId: string) => {
    setExpandedScopes((prev) => ({ ...prev, [journalId]: !prev[journalId] }));
  };

  // Client-side UTF-8 BOM CSV export (Part B)
  const handleDownloadCsv = () => {
    if (!compareData) return;

    const visibleRows = compareData.rows.filter((row) => {
      if (collapsedGroups[row.group]) return false;
      if (onlyDifferences && row.allSame) return false;
      return true;
    });

    const headerCells = ['Metric', ...compareData.journals.map((j) => j.title)];
    const lines: string[] = [headerCells.map(escapeCsvCell).join(',')];

    for (const row of visibleRows) {
      const rowCells = [
        row.label,
        ...row.values.map((cell) => formatCellValueForCsv(row, cell.value)),
      ];
      lines.push(rowCells.map(escapeCsvCell).join(','));
    }

    const csvContent = `\uFEFF${lines.join('\r\n')}`;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'publishaid-journal-comparison.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const renderCellContent = (
    row: CompareRow,
    value: any,
    journal: CompareJournalHeader,
    isBest: boolean,
    rulesSourceForJournal: unknown
  ) => {
    // Part B: unextracted journal guidelines in requirements section
    if (row.key === 'rulesSource' && (value === null || value === undefined)) {
      return (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-slate-400 italic">Not extracted yet</span>
          <Link
            to={`/guidelines?journalId=${encodeURIComponent(journal.id)}`}
            className="text-xs font-semibold text-[#0F766E] hover:underline inline-flex items-center gap-1"
          >
            Extract rules
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      );
    }

    if (value === null || value === undefined) {
      const tooltipText =
        row.group === 'requirements' && !rulesSourceForJournal
          ? 'No active guideline ruleset for this journal'
          : 'Not available from our data sources';
      return (
        <span
          className="text-slate-400 font-normal cursor-help"
          title={tooltipText}
        >
          N/A
        </span>
      );
    }

    let formattedNode: React.ReactNode;

    if (row.key === 'apcUsd' && typeof value === 'number') {
      if (value === 0) {
        formattedNode = (
          <span title="Listed as free to publish" className="cursor-help">
            $0
          </span>
        );
      } else {
        formattedNode = `$${Math.round(value).toLocaleString('en-US')}`;
      }
    } else if (row.key === 'reviewWeeks' && typeof value === 'number') {
      formattedNode = formatReviewWeeks(value);
    } else if (row.key === 'acceptanceRate' && typeof value === 'number') {
      formattedNode = `${value.toFixed(1)}%`;
    } else if (row.key === 'matchScore' && typeof value === 'number') {
      formattedNode = `${Math.round(value)}%`;
    } else if ((row.key === 'citeScore' || row.key === 'impactFactor') && typeof value === 'number') {
      formattedNode = value.toFixed(1);
    } else if ((row.key === 'sjr' || row.key === 'citedness2yr') && typeof value === 'number') {
      formattedNode = value.toFixed(2);
    } else if (row.type === 'integer' && typeof value === 'number') {
      formattedNode = Math.round(value).toLocaleString('en-US');
    } else if (row.key === 'quartile') {
      formattedNode = <StatusBadge status={String(value)} />;
    } else if (row.type === 'link' && typeof value === 'string') {
      formattedNode = (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#0F766E] hover:underline inline-flex items-center gap-1 font-medium break-all"
        >
          Visit site
          <ExternalLink className="w-3 h-3 shrink-0" />
        </a>
      );
    } else if (row.type === 'list' && Array.isArray(value)) {
      formattedNode = (
        <div className="flex flex-wrap gap-1">
          {value.map((item, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[11px] font-medium"
            >
              {String(item)}
            </span>
          ))}
        </div>
      );
    } else if (row.type === 'longtext') {
      const fullText = String(value).replace(/\\n/g, '\n');
      const isLong = fullText.length > 300;
      const isExpanded = !!expandedScopes[journal.id];
      const shownText = isLong && !isExpanded ? `${fullText.slice(0, 300).trimEnd()}...` : fullText;
      formattedNode = (
        <div className="space-y-1.5 leading-relaxed whitespace-pre-line">
          <p>{shownText}</p>
          {isLong && (
            <button
              type="button"
              onClick={() => toggleScopeExpanded(journal.id)}
              className="text-[11px] font-semibold text-[#0F766E] hover:underline cursor-pointer"
            >
              {isExpanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>
      );
    } else {
      formattedNode = String(value);
    }

    return (
      <div className="flex items-start justify-between gap-2">
        <div className={isBest ? 'font-bold text-[#0F766E]' : 'text-slate-700 font-medium'}>
          {formattedNode}
        </div>
        {isBest && (
          <span className="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#CCFBF1] text-[#0F766E] border border-[#99F6E4]">
            <Check className="w-3 h-3" />
            Best
          </span>
        )}
      </div>
    );
  };

  // Map chip labels using loaded headers, single-chip cache, or context
  const chipItems = useMemo(() => {
    const headerMap = new Map<string, string>();
    if (compareData?.journals) {
      compareData.journals.forEach((j) => headerMap.set(j.id, j.title));
    }
    return activeIds.map((id) => {
      const label =
        headerMap.get(id) ||
        singleChipLabelMap[id] ||
        contextJournals.find((j) => j.id === id)?.title ||
        `Journal #${id}`;
      return { id, label };
    });
  }, [activeIds, compareData, singleChipLabelMap, contextJournals]);

  const rulesSourceRow = useMemo(
    () => compareData?.rows.find((r) => r.key === 'rulesSource'),
    [compareData]
  );

  const visibleGroupSections = useMemo(() => {
    if (!compareData) return [];
    return compareData.groups
      .map((group) => {
        const rows = compareData.rows.filter(
          (row) => row.group === group.key && (!onlyDifferences || !row.allSame)
        );
        return { group, rows };
      })
      .filter((sec) => sec.rows.length > 0);
  }, [compareData, onlyDifferences]);

  const dbProjects = useMemo(
    () => projects.filter((p) => /^\d+$/.test(p.id)),
    [projects]
  );

  return (
    <div className="space-y-6">
      {/* Page Title & Primary Actions */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
            Compare candidate journals
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Review publishing models, prestige, speed, and requirements side by side before choosing your target venue.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <Button
            variant="secondary"
            onClick={() => setIsAddModalOpen(true)}
            disabled={activeIds.length >= 4}
            title={
              activeIds.length >= 4
                ? 'At most four journals can be compared at one time.'
                : 'Add another journal to compare'
            }
            leftIcon={<Plus className="w-4 h-4 text-[#0F766E]" />}
            className="shadow-2xs"
          >
            Add journal
          </Button>

          {compareData && (
            <Button
              variant="secondary"
              onClick={handleDownloadCsv}
              leftIcon={<Download className="w-4 h-4 text-[#0F766E]" />}
              className="shadow-2xs"
            >
              Download CSV
            </Button>
          )}
        </div>
      </div>

      {/* Sub-bar & Removable Chips */}
      <div className="bg-white rounded-2xl border border-slate-200/90 p-4 shadow-2xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-slate-500 font-medium">Project context:</span>
            {activeDbProjectId && activeProject ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#CCFBF1]/60 text-[#0F766E] font-semibold border border-[#99F6E4]">
                {activeProject.title}
              </span>
            ) : (
              <span className="text-slate-400 italic">
                None selected (open a workspace to view manuscript fit scores)
              </span>
            )}
          </div>

          <div className="text-slate-500 font-medium">
            {activeIds.length} of 4 journals selected
          </div>
        </div>

        {/* Selected Chips */}
        {chipItems.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap pt-1 border-t border-slate-100">
            {chipItems.map((chip) => (
              <span
                key={chip.id}
                className="inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-[#14283D] border border-slate-200"
              >
                <span className="max-w-[240px] truncate">{chip.label}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveJournal(chip.id)}
                  aria-label={`Remove ${chip.label} from comparison`}
                  title={`Remove ${chip.label}`}
                  className="p-0.5 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Toolbar Toggles (shown when table active or loading) */}
        {activeIds.length >= 2 && (
          <div className="flex flex-wrap items-center gap-5 pt-2 border-t border-slate-100 text-xs">
            <label className="inline-flex items-center gap-2 cursor-pointer select-none font-medium text-slate-700">
              <input
                type="checkbox"
                checked={onlyDifferences}
                onChange={(e) => setOnlyDifferences(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-[#0F766E] focus:ring-[#0F766E] cursor-pointer"
              />
              <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
              Show only rows that differ
            </label>

            <label className="inline-flex items-center gap-2 cursor-pointer select-none font-medium text-slate-700">
              <input
                type="checkbox"
                checked={includeRequirements}
                onChange={(e) => setIncludeRequirements(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-[#0F766E] focus:ring-[#0F766E] cursor-pointer"
              />
              Include submission requirements
            </label>
          </div>
        )}
      </div>

      {/* Inline Notifications */}
      {bannerAlert && (
        <div
          role="alert"
          className={`p-3.5 rounded-xl border flex items-center justify-between text-xs ${
            bannerAlert.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : bannerAlert.type === 'warning'
              ? 'bg-amber-50 border-amber-200 text-amber-800'
              : bannerAlert.type === 'error'
              ? 'bg-rose-50 border-rose-200 text-rose-800'
              : 'bg-sky-50 border-sky-200 text-sky-800'
          }`}
        >
          <div className="flex items-center gap-2">
            {bannerAlert.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0" />
            )}
            <span className="font-medium">{bannerAlert.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setBannerAlert(null)}
            className="font-bold ml-3 opacity-70 hover:opacity-100 cursor-pointer"
          >
            ×
          </button>
        </div>
      )}

      {/* Main Content */}
      {activeIds.length < 2 ? (
        <div className="bg-white rounded-2xl border border-slate-200/90 p-10 text-center space-y-4 shadow-2xs">
          <div className="w-14 h-14 rounded-2xl bg-[#CCFBF1] text-[#0F766E] flex items-center justify-center mx-auto">
            <Columns2 className="w-7 h-7" />
          </div>
          <div className="space-y-1.5 max-w-md mx-auto">
            <h2 className="text-lg font-bold text-[#14283D]">
              Select two to four journals to compare
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 leading-relaxed">
              {activeIds.length === 1
                ? 'One journal is selected. Add at least one more journal from your shortlist or the catalog to start comparing metrics side by side.'
                : 'Choose at least two candidate journals from Journal Finder, Browse Catalog, or click Add journal above.'}
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 flex-wrap pt-2">
            <Button
              onClick={() => setIsAddModalOpen(true)}
              leftIcon={<Plus className="w-4 h-4" />}
            >
              Add journal
            </Button>
            <Button
              variant="secondary"
              onClick={() => navigate('/finder')}
              leftIcon={<Search className="w-4 h-4 text-[#0F766E]" />}
            >
              Open Journal Finder
            </Button>
            <Button
              variant="secondary"
              onClick={() => navigate('/browse')}
            >
              Browse Catalog
            </Button>
          </div>
        </div>
      ) : isLoadingCompare && !compareData ? (
        <div className="bg-white rounded-2xl border border-slate-200/90 p-16 flex flex-col items-center justify-center space-y-3 shadow-2xs">
          <Loader2 className="w-8 h-8 text-[#0F766E] animate-spin" />
          <p className="text-sm font-medium text-slate-600">Loading side-by-side comparison...</p>
        </div>
      ) : compareData ? (
        <>
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full w-full text-left border-collapse">
                {/* Column Headers */}
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70">
                    <th
                      scope="col"
                      className="sticky left-0 z-20 bg-slate-50 p-5 w-[210px] min-w-[210px] text-xs font-bold uppercase tracking-wider text-slate-400 align-top border-r border-slate-200/80"
                    >
                      METRIC
                    </th>
                    {compareData.journals.map((journal) => {
                      const isTarget = !!journal.projectContext?.isTarget;
                      return (
                        <th
                          key={journal.id}
                          scope="col"
                          className="p-5 align-top min-w-[240px] border-l border-slate-100"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="space-y-1.5">
                              {isTarget && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#0F766E] text-white">
                                  <CheckCircle2 className="w-3 h-3" />
                                  Primary target
                                </span>
                              )}
                              <h3 className="font-bold text-base text-[#14283D] leading-snug">
                                {journal.title}
                              </h3>
                              <p className="text-xs text-slate-400 font-normal">
                                {journal.publisher}
                              </p>
                            </div>

                            <button
                              type="button"
                              onClick={() => handleRemoveJournal(journal.id)}
                              title={`Remove ${journal.title}`}
                              aria-label={`Remove ${journal.title}`}
                              className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-200/60 transition-colors cursor-pointer shrink-0"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>

                {/* Grouped Metric Rows */}
                <tbody className="divide-y divide-slate-100 text-xs">
                  {visibleGroupSections.length === 0 ? (
                    <tr>
                      <td
                        colSpan={compareData.journals.length + 1}
                        className="p-8 text-center text-slate-500"
                      >
                        All displayed metrics are identical across the selected journals. Turn off &ldquo;Show only rows that differ&rdquo; to view all rows.
                      </td>
                    </tr>
                  ) : (
                    visibleGroupSections.map(({ group, rows }) => {
                      const isCollapsed = !!collapsedGroups[group.key];
                      return (
                        <React.Fragment key={group.key}>
                          {/* Collapsible Group Header */}
                          <tr className="bg-slate-50/90 border-y border-slate-200/70">
                            <th
                              colSpan={compareData.journals.length + 1}
                              scope="colgroup"
                              className="p-0"
                            >
                              <button
                                type="button"
                                onClick={() => toggleGroupCollapsed(group.key)}
                                className="w-full px-5 py-2.5 flex items-center gap-2 text-left text-[11px] font-bold uppercase tracking-wider text-slate-600 hover:text-[#14283D] cursor-pointer"
                              >
                                {isCollapsed ? (
                                  <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                                ) : (
                                  <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                                )}
                                <span>{group.label}</span>
                                <span className="text-[10px] font-medium text-slate-400 normal-case">
                                  ({rows.length})
                                </span>
                              </button>
                            </th>
                          </tr>

                          {!isCollapsed &&
                            rows.map((row) => (
                              <tr key={row.key} className="hover:bg-slate-50/50 transition-colors">
                                <th
                                  scope="row"
                                  className="sticky left-0 z-10 bg-white p-5 font-semibold text-slate-700 align-top border-r border-slate-200/80"
                                >
                                  <div>{row.label}</div>
                                  {row.note && (
                                    <div className="text-[11px] font-normal text-slate-400 mt-0.5 leading-snug">
                                      {row.note}
                                    </div>
                                  )}
                                </th>

                                {row.values.map((cell, colIdx) => {
                                  const journal = compareData.journals[colIdx];
                                  const rulesSourceVal = rulesSourceRow?.values[colIdx]?.value;
                                  return (
                                    <td
                                      key={journal.id}
                                      className="p-5 align-top border-l border-slate-100"
                                    >
                                      {renderCellContent(
                                        row,
                                        cell.value,
                                        journal,
                                        cell.isBest,
                                        rulesSourceVal
                                      )}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>

                {/* Column Footer & Primary Target Selection */}
                <tfoot>
                  <tr className="bg-slate-50/70 border-t border-slate-200 text-xs">
                    <th
                      scope="row"
                      className="sticky left-0 z-10 bg-slate-50 p-5 font-semibold text-slate-500 align-top border-r border-slate-200/80"
                    >
                      <div>Completeness &amp; Action</div>
                      <div className="text-[11px] font-normal text-slate-400 mt-0.5">
                        Core catalog fields &amp; primary target
                      </div>
                    </th>
                    {compareData.journals.map((journal) => {
                      const isTarget = !!journal.projectContext?.isTarget;
                      const formattedDate = formatUpdatedDate(journal.metadataUpdatedAt);
                      return (
                        <td
                          key={journal.id}
                          className="p-5 align-top border-l border-slate-100 space-y-3"
                        >
                          <div className="space-y-1 text-[11px] text-slate-500">
                            <div className="font-semibold text-slate-700">
                              {journal.completeness.available} of {journal.completeness.total} metrics available
                            </div>
                            {formattedDate && (
                              <div className="text-slate-400">Updated {formattedDate}</div>
                            )}
                          </div>

                          <Button
                            size="sm"
                            variant={isTarget ? 'primary' : 'secondary'}
                            disabled={isTarget || isSettingTargetId === journal.id}
                            isLoading={isSettingTargetId === journal.id}
                            onClick={() => handleSetTargetClick(journal)}
                            leftIcon={
                              isTarget ? (
                                <CheckCircle2 className="w-3.5 h-3.5" />
                              ) : (
                                <Bookmark className="w-3.5 h-3.5 text-[#0F766E]" />
                              )
                            }
                            className="w-full shadow-2xs"
                          >
                            {isTarget ? 'Primary target' : 'Set as primary target'}
                          </Button>
                        </td>
                      );
                    })}
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Expandable Data Notes Banner */}
          <div className="bg-[#F0FDF4] border border-[#DCFCE7] rounded-2xl p-4 text-xs text-[#166534] space-y-2">
            <button
              type="button"
              onClick={() => setShowNotes((prev) => !prev)}
              className="w-full flex items-center justify-between font-semibold cursor-pointer text-left"
            >
              <span className="flex items-center gap-2">
                <Info className="w-4 h-4 shrink-0 text-[#16A34A]" />
                Data sources &amp; comparison notes
              </span>
              {showNotes ? (
                <ChevronDown className="w-4 h-4 text-[#16A34A]" />
              ) : (
                <ChevronRight className="w-4 h-4 text-[#16A34A]" />
              )}
            </button>

            {showNotes && (
              <ul className="list-disc pl-6 space-y-1 text-[11px] text-[#15803D]">
                {compareData.notes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
                <li>
                  Best markers highlight optimal non-missing values per metric row; no overall composite score is computed.
                </li>
                {includeRequirements && (
                  <li>
                    General formatting rules are shown by default; individual journals may specify article-type overrides.
                  </li>
                )}
              </ul>
            )}
          </div>
        </>
      ) : null}

      {/* Add Journal Picker Modal */}
      {isAddModalOpen && (
        <div
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4"
          onClick={() => setIsAddModalOpen(false)}
        >
          <div
            className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 space-y-4 max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-[#14283D]">Add Journal to Comparison</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Select from your active project shortlist or search the verified journal catalog (max 4).
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-2 border-b border-slate-100 pb-2">
              <button
                type="button"
                onClick={() => setPickerTab('catalog')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
                  pickerTab === 'catalog'
                    ? 'bg-[#0F766E] text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                Search catalog
              </button>
              <button
                type="button"
                onClick={() => setPickerTab('shortlist')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
                  pickerTab === 'shortlist'
                    ? 'bg-[#0F766E] text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                From my shortlist{activeDbProjectId && !isLoadingShortlist ? ` (${shortlistItems.length})` : ''}
              </button>
            </div>

            {pickerTab === 'catalog' ? (
              <>
                <div className="relative">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={catalogSearch}
                    onChange={(e) => setCatalogSearch(e.target.value)}
                    placeholder="Search journals by title, publisher, ISSN, or subject..."
                    className="w-full pl-10 pr-4 h-[38px] rounded-xl border border-slate-200 text-xs focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none"
                  />
                </div>

                <div className="space-y-2 overflow-y-auto flex-1 pr-1 min-h-[220px] max-h-[340px]">
                  {isLoadingCatalog ? (
                    <div className="py-10 flex flex-col items-center justify-center text-slate-500 text-xs gap-2">
                      <Loader2 className="w-5 h-5 animate-spin text-[#0F766E]" />
                      Searching catalog...
                    </div>
                  ) : catalogItems.length === 0 ? (
                    <div className="py-10 text-center text-xs text-slate-500">
                      No matching journals found.
                    </div>
                  ) : (
                    catalogItems.map((j) => {
                      const isSelected = activeIds.includes(j.id);
                      const isDisabled = isSelected || activeIds.length >= 4;
                      return (
                        <button
                          key={j.id}
                          type="button"
                          disabled={isDisabled}
                          onClick={() => handleAddJournal(j)}
                          className={`w-full text-left p-3 rounded-xl border flex items-center justify-between transition-all ${
                            isSelected
                              ? 'border-[#0F766E]/40 bg-[#CCFBF1]/20 opacity-65 cursor-not-allowed'
                              : isDisabled
                              ? 'border-slate-200 opacity-50 cursor-not-allowed'
                              : 'border-slate-200 hover:bg-slate-50 cursor-pointer'
                          }`}
                        >
                          <div className="min-w-0 pr-3">
                            <p className="text-xs font-semibold text-[#14283D] truncate">{j.title}</p>
                            <p className="text-[11px] text-slate-400 truncate">
                              {j.publisher}
                              {j.quartile ? ` · ${j.quartile}` : ''}
                              {j.subjectCategory ? ` · ${j.subjectCategory}` : ''}
                            </p>
                          </div>
                          {isSelected ? (
                            <span className="text-[11px] font-semibold text-[#0F766E] shrink-0 flex items-center gap-1">
                              <Check className="w-3.5 h-3.5" />
                              Selected
                            </span>
                          ) : (
                            <Plus className="w-4 h-4 text-[#0F766E] shrink-0" />
                          )}
                        </button>
                      );
                    })
                  )}
                </div>
              </>
            ) : (
              <div className="space-y-2 overflow-y-auto flex-1 pr-1 min-h-[220px] max-h-[340px]">
                {!activeDbProjectId ? (
                  <div className="py-10 text-center space-y-2 text-xs text-slate-500">
                    <p>Select an active project workspace to view its shortlisted journals.</p>
                    <button
                      type="button"
                      onClick={() => setPickerTab('catalog')}
                      className="text-[#0F766E] font-semibold hover:underline cursor-pointer"
                    >
                      Search the full catalog instead
                    </button>
                  </div>
                ) : isLoadingShortlist ? (
                  <div className="py-10 flex flex-col items-center justify-center text-slate-500 text-xs gap-2">
                    <Loader2 className="w-5 h-5 animate-spin text-[#0F766E]" />
                    Loading shortlist...
                  </div>
                ) : shortlistItems.length === 0 ? (
                  <div className="py-10 text-center space-y-2 text-xs text-slate-500">
                    <p>No journals shortlisted in &ldquo;{activeProject?.title}&rdquo; yet.</p>
                    <button
                      type="button"
                      onClick={() => navigate('/finder')}
                      className="text-[#0F766E] font-semibold hover:underline cursor-pointer"
                    >
                      Discover journals in Journal Finder
                    </button>
                  </div>
                ) : (
                  shortlistItems.map((j) => {
                    const isSelected = activeIds.includes(j.id);
                    const isDisabled = isSelected || activeIds.length >= 4;
                    return (
                      <button
                        key={j.id}
                        type="button"
                        disabled={isDisabled}
                        onClick={() => handleAddJournal(j)}
                        className={`w-full text-left p-3 rounded-xl border flex items-center justify-between transition-all ${
                          isSelected
                            ? 'border-[#0F766E]/40 bg-[#CCFBF1]/20 opacity-65 cursor-not-allowed'
                            : isDisabled
                            ? 'border-slate-200 opacity-50 cursor-not-allowed'
                            : 'border-slate-200 hover:bg-slate-50 cursor-pointer'
                        }`}
                      >
                        <div className="min-w-0 pr-3">
                          <p className="text-xs font-semibold text-[#14283D] truncate">{j.title}</p>
                          <p className="text-[11px] text-slate-400 truncate">
                            {j.publisher}
                            {j.quartile ? ` · ${j.quartile}` : ''}
                            {j.matchScore != null ? ` · ${j.matchScore}% match` : ''}
                          </p>
                        </div>
                        {isSelected ? (
                          <span className="text-[11px] font-semibold text-[#0F766E] shrink-0 flex items-center gap-1">
                            <Check className="w-3.5 h-3.5" />
                            Selected
                          </span>
                        ) : (
                          <Plus className="w-4 h-4 text-[#0F766E] shrink-0" />
                        )}
                      </button>
                    );
                  })
                )}
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-slate-100">
              <Button onClick={() => setIsAddModalOpen(false)}>Done</Button>
            </div>
          </div>
        </div>
      )}

      {/* Project Chooser Modal (when setting target without an active workspace) */}
      {pendingTargetJournal && (
        <div
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4"
          onClick={() => setPendingTargetJournal(null)}
        >
          <div
            className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-[#14283D]">Choose a Project Workspace</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Select an existing workspace or create a new one to set{' '}
                  <strong className="text-[#14283D]">{pendingTargetJournal.title}</strong> as its primary target.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPendingTargetJournal(null)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {chooserError && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800">
                {chooserError}
              </div>
            )}

            {dbProjects.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Existing Workspaces
                </h4>
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {dbProjects.map((proj) => (
                    <button
                      key={proj.id}
                      type="button"
                      disabled={isSettingTargetId === pendingTargetJournal.id}
                      onClick={() => handleSelectExistingProject(proj.id, proj.title)}
                      className="w-full text-left p-3 rounded-xl border border-slate-200 hover:border-[#0F766E] hover:bg-[#CCFBF1]/15 flex items-center justify-between transition-all cursor-pointer"
                    >
                      <div className="min-w-0 pr-3">
                        <div className="text-xs font-semibold text-[#14283D] truncate">
                          {proj.title}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate">
                          {proj.researchField || proj.field || 'Research workspace'}
                          {proj.targetJournalTitle ? ` · Current target: ${proj.targetJournalTitle}` : ''}
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-[#0F766E] shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Inline Project Creation Form */}
            <form onSubmit={handleCreateAndAssignProject} className="space-y-3 pt-3 border-t border-slate-100">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <FolderPlus className="w-3.5 h-3.5 text-[#0F766E]" />
                Or Create New Workspace
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <input
                  type="text"
                  value={newProjectTitle}
                  onChange={(e) => setNewProjectTitle(e.target.value)}
                  placeholder="Workspace title *"
                  className="w-full px-3 h-[38px] rounded-xl border border-slate-300 text-xs focus:border-[#0F766E] outline-none"
                />
                <input
                  type="text"
                  value={newProjectField}
                  onChange={(e) => setNewProjectField(e.target.value)}
                  placeholder="Research field"
                  className="w-full px-3 h-[38px] rounded-xl border border-slate-300 text-xs focus:border-[#0F766E] outline-none"
                />
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setPendingTargetJournal(null)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  isLoading={isCreatingProject || isSettingTargetId === pendingTargetJournal.id}
                >
                  Create &amp; Set Target
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
