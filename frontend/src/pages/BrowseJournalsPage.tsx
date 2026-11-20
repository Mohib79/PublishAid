import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Filter,
  Bookmark,
  BookmarkCheck,
  Columns2,
  LayoutGrid,
  List,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  ArrowUpDown,
  RotateCcw,
  ExternalLink,
  X,
  Info,
  Building2,
  Hash,
  Clock,
  Percent,
  TrendingUp,
  FileText,
  AlertCircle,
  Loader2,
  Check,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/StatusBadge';
import { CustomDropdown } from '../components/common/CustomDropdown';
import { browseJournals, BrowseJournalsResponse } from '../lib/api';
import { Journal } from '../types';

export const BrowseJournalsPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    mergeJournals,
    toggleShortlistJournal,
    selectedCompareJournalIds,
    toggleCompareJournal,
    compareNotification,
    clearCompareNotification,
    journals: contextJournals,
  } = useApp();

  // Filter & Search states
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedPublisher, setSelectedPublisher] = useState('all');
  const [selectedQuartile, setSelectedQuartile] = useState('all');
  const [selectedOaType, setSelectedOaType] = useState('all');
  const [sortBy, setSortBy] = useState('title');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [filterShortlistedOnly, setFilterShortlistedOnly] = useState(false);

  // Pagination states
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // View mode
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');

  // API Data & Loading states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [browseData, setBrowseData] = useState<BrowseJournalsResponse>({
    items: [],
    total: 0,
    page: 1,
    limit: 10,
    totalPages: 1,
    categories: [],
    publishers: [],
  });

  // Selected Journal for Details Modal
  const [selectedModalJournal, setSelectedModalJournal] = useState<Journal | null>(null);
  const [copiedScope, setCopiedScope] = useState(false);

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setCurrentPage(1); // Reset to page 1 on new search
    }, 300);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Fetch journals from DB API
  const fetchJournals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await browseJournals({
        search: debouncedSearch,
        category: selectedCategory,
        publisher: selectedPublisher,
        quartile: selectedQuartile,
        openAccessType: selectedOaType,
        sortBy,
        sortOrder,
        page: currentPage,
        limit: pageSize,
      });
      setBrowseData(res);
      mergeJournals(res.items || []);
    } catch (err: any) {
      console.error('Failed to browse journals:', err);
      setError(err.message || 'Failed to load journals from the database.');
    } finally {
      setLoading(false);
    }
  }, [
    debouncedSearch,
    selectedCategory,
    selectedPublisher,
    selectedQuartile,
    selectedOaType,
    sortBy,
    sortOrder,
    currentPage,
    pageSize,
    mergeJournals,
  ]);

  useEffect(() => {
    fetchJournals();
  }, [fetchJournals]);

  // Reset all filters
  const handleResetFilters = () => {
    setSearchTerm('');
    setDebouncedSearch('');
    setSelectedCategory('all');
    setSelectedPublisher('all');
    setSelectedQuartile('all');
    setSelectedOaType('all');
    setSortBy('title');
    setSortOrder('asc');
    setFilterShortlistedOnly(false);
    setCurrentPage(1);
  };

  const hasActiveFilters =
    searchTerm !== '' ||
    selectedCategory !== 'all' ||
    selectedPublisher !== 'all' ||
    selectedQuartile !== 'all' ||
    selectedOaType !== 'all' ||
    sortBy !== 'title' ||
    filterShortlistedOnly;

  // Check shortlist state using context
  const isJournalShortlisted = (journalId: string) => {
    const fromContext = contextJournals.find((j) => j.id === journalId);
    return fromContext ? fromContext.isShortlisted : false;
  };

  const isJournalCompared = (journalId: string) => {
    return selectedCompareJournalIds.includes(journalId);
  };

  const handleCopyScope = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedScope(true);
    setTimeout(() => setCopiedScope(false), 2000);
  };

  const shortlistedJournals = useMemo(() => {
    return contextJournals.filter((j) => j.isShortlisted && /^\d+$/.test(j.id));
  }, [contextJournals]);
  const totalShortlistedCount = shortlistedJournals.length;

  // Filtered shortlist when filterShortlistedOnly is active
  const filteredShortlist = useMemo(() => {
    if (!filterShortlistedOnly) return [];
    let list = [...shortlistedJournals];

    if (debouncedSearch.trim()) {
      const q = debouncedSearch.trim().toLowerCase();
      list = list.filter(
        (j) =>
          j.title.toLowerCase().includes(q) ||
          (j.publisher && j.publisher.toLowerCase().includes(q)) ||
          (j.subjectCategory && j.subjectCategory.toLowerCase().includes(q)) ||
          (j.issn && j.issn.toLowerCase().includes(q)) ||
          (j.aimsAndScope && j.aimsAndScope.toLowerCase().includes(q))
      );
    }
    if (selectedCategory !== 'all') {
      list = list.filter((j) => j.subjectCategory === selectedCategory);
    }
    if (selectedPublisher !== 'all') {
      list = list.filter((j) => j.publisher === selectedPublisher);
    }
    if (selectedQuartile !== 'all') {
      list = list.filter((j) => j.quartile === selectedQuartile);
    }
    if (selectedOaType !== 'all') {
      list = list.filter((j) => j.openAccessType === selectedOaType);
    }

    // Sort
    list.sort((a, b) => {
      let valA: any =
        (a as any)[sortBy] ??
        (sortBy === 'citescore'
          ? a.citeScore
          : sortBy === 'impact_factor'
          ? a.impactFactor
          : sortBy === 'review_weeks'
          ? a.reviewWeeks
          : sortBy === 'acceptance_rate'
          ? a.acceptanceRate
          : null);
      let valB: any =
        (b as any)[sortBy] ??
        (sortBy === 'citescore'
          ? b.citeScore
          : sortBy === 'impact_factor'
          ? b.impactFactor
          : sortBy === 'review_weeks'
          ? b.reviewWeeks
          : sortBy === 'acceptance_rate'
          ? b.acceptanceRate
          : null);

      if (valA == null && valB == null) return 0;
      if (valA == null) return 1;
      if (valB == null) return -1;

      if (typeof valA === 'string' && typeof valB === 'string') {
        return sortOrder === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return sortOrder === 'asc' ? (valA > valB ? 1 : -1) : (valA < valB ? 1 : -1);
    });

    return list;
  }, [
    filterShortlistedOnly,
    shortlistedJournals,
    debouncedSearch,
    selectedCategory,
    selectedPublisher,
    selectedQuartile,
    selectedOaType,
    sortBy,
    sortOrder,
  ]);

  const activeTotal = filterShortlistedOnly ? filteredShortlist.length : browseData.total;
  const activeTotalPages = filterShortlistedOnly
    ? Math.max(1, Math.ceil(filteredShortlist.length / pageSize))
    : browseData.totalPages;
  const activeItems = filterShortlistedOnly
    ? filteredShortlist.slice((currentPage - 1) * pageSize, currentPage * pageSize)
    : browseData.items;

  return (
    <div className="space-y-6">
      {/* 1. Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
              Browse Journal Catalog
            </h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#CCFBF1] text-[#0F766E] border border-[#99F6E4]/70 whitespace-nowrap shrink-0">
              {browseData.total} Verified Venues
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Explore and filter all 50 peer-reviewed journals stored in the PublishAid database.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap shrink-0">
          <Button
            variant={selectedCompareJournalIds.length >= 2 ? 'primary' : 'secondary'}
            disabled={selectedCompareJournalIds.length < 2}
            onClick={() => navigate(`/compare?ids=${selectedCompareJournalIds.join(',')}`)}
            leftIcon={<Columns2 className="w-4 h-4" />}
            className="shadow-2xs text-xs sm:text-sm"
          >
            Compare Selected ({selectedCompareJournalIds.length})
          </Button>

          <Button
            variant={filterShortlistedOnly ? 'primary' : 'secondary'}
            onClick={() => {
              setFilterShortlistedOnly((prev) => !prev);
              setCurrentPage(1);
            }}
            leftIcon={
              filterShortlistedOnly ? (
                <BookmarkCheck className="w-4 h-4 text-white" />
              ) : (
                <Bookmark className="w-4 h-4 text-[#0F766E]" />
              )
            }
            className="shadow-2xs text-xs sm:text-sm"
          >
            {filterShortlistedOnly
              ? `Shortlisted Only (${totalShortlistedCount})`
              : `My Shortlist (${totalShortlistedCount})`}
          </Button>

          <Button
            variant="mint"
            onClick={() => navigate('/finder')}
            leftIcon={<Search className="w-4 h-4" />}
            className="shadow-2xs text-xs sm:text-sm"
          >
            Semantic Matcher
          </Button>
        </div>
      </div>

      {compareNotification && (
        <div
          role="alert"
          className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between text-xs text-amber-800"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-amber-600" />
            <span className="font-medium">{compareNotification}</span>
          </div>
          <button
            type="button"
            onClick={clearCompareNotification}
            className="text-amber-600 hover:text-amber-900 font-bold ml-3 cursor-pointer"
          >
            ×
          </button>
        </div>
      )}

      {/* 2. Search & Filter Bar */}
      <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs space-y-4">
        {/* Search Input Row */}
        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by journal title, publisher, subject, ISSN, or keywords..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-10 py-2.5 bg-slate-50/70 hover:bg-slate-50 focus:bg-white text-sm text-slate-800 placeholder-slate-400 rounded-xl border border-slate-200 focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 transition-all outline-none"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Sort By Selector */}
          <div className="flex items-center gap-2 shrink-0 justify-between sm:justify-start">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider hidden sm:inline">
              Sort:
            </span>
            <div className="relative flex-1 sm:flex-initial min-w-[190px]">
              <CustomDropdown
                value={sortBy}
                onChange={(val) => {
                  setSortBy(val);
                  if (val === 'title') {
                    setSortOrder('asc');
                  } else {
                    setSortOrder('desc');
                  }
                  setCurrentPage(1);
                }}
                options={[
                  { value: 'title', label: 'Title (A-Z)' },
                  { value: 'citescore', label: 'CiteScore (Highest)' },
                  { value: 'impact_factor', label: 'Impact Factor (Highest)' },
                  { value: 'acceptance_rate', label: 'Acceptance Rate (Highest)' },
                  { value: 'review_weeks', label: 'First Decision Time (Fastest)' },
                ]}
                size="md"
              />
            </div>

            {/* Sort Direction Toggle */}
            <button
              onClick={() => setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))}
              title={`Sort order: ${sortOrder === 'asc' ? 'Ascending' : 'Descending'}`}
              className="p-2.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer shrink-0"
            >
              <ArrowUpDown className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Filters Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 pt-2 border-t border-slate-100 items-end">
          {/* Category Filter */}
          <div>
            <CustomDropdown
              label="Subject Area"
              value={selectedCategory}
              onChange={(val) => {
                setSelectedCategory(val);
                setCurrentPage(1);
              }}
              options={[
                { value: 'all', label: `All Subjects (${browseData.categories.length})` },
                ...browseData.categories.map((cat) => ({ value: cat, label: cat })),
              ]}
              searchable={browseData.categories.length > 8}
              searchPlaceholder="Search subjects..."
              size="sm"
            />
          </div>

          {/* Publisher Filter */}
          <div>
            <CustomDropdown
              label="Publisher"
              value={selectedPublisher}
              onChange={(val) => {
                setSelectedPublisher(val);
                setCurrentPage(1);
              }}
              options={[
                { value: 'all', label: `All Publishers (${browseData.publishers.length})` },
                ...browseData.publishers.map((pub) => ({ value: pub, label: pub })),
              ]}
              searchable={browseData.publishers.length > 8}
              searchPlaceholder="Search publishers..."
              size="sm"
            />
          </div>

          {/* Quartile Filter */}
          <div>
            <CustomDropdown
              label="Quartile"
              value={selectedQuartile}
              onChange={(val) => {
                setSelectedQuartile(val);
                setCurrentPage(1);
              }}
              options={[
                { value: 'all', label: 'All Quartiles' },
                { value: 'Q1', label: 'Q1 (Top 25%)' },
                { value: 'Q2', label: 'Q2' },
                { value: 'Q3', label: 'Q3' },
                { value: 'Q4', label: 'Q4' },
              ]}
              size="sm"
            />
          </div>

          {/* Open Access Filter */}
          <div>
            <CustomDropdown
              label="Access Model"
              value={selectedOaType}
              onChange={(val) => {
                setSelectedOaType(val);
                setCurrentPage(1);
              }}
              options={[
                { value: 'all', label: 'All Models' },
                { value: 'Hybrid', label: 'Hybrid' },
                { value: 'Open access', label: 'Open Access' },
                { value: 'Subscription', label: 'Subscription' },
              ]}
              size="sm"
            />
          </div>

          {/* Reset Action */}
          <div className="col-span-2 sm:col-span-4 lg:col-span-1 flex items-end justify-end pt-3 sm:pt-0">
            {hasActiveFilters ? (
              <button
                onClick={handleResetFilters}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 px-3 py-2 rounded-lg border border-rose-200 transition-colors cursor-pointer w-full justify-center"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset Filters
              </button>
            ) : (
              <span className="text-xs text-slate-400 py-2 italic text-center w-full">
                No filters applied
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 3. Toolbar & View Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span>
            Showing{' '}
            <strong className="text-slate-800 font-semibold">
              {activeTotal === 0
                ? 0
                : (currentPage - 1) * pageSize + 1}
              –
              {Math.min(currentPage * pageSize, activeTotal)}
            </strong>{' '}
            of <strong className="text-slate-800 font-semibold">{activeTotal}</strong>{' '}
            {filterShortlistedOnly ? 'shortlisted journals' : 'journals'}
          </span>

          {hasActiveFilters && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
              Filtered
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 self-end sm:self-auto">
          {/* Per Page Selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 text-xs">Rows:</span>
            <div className="w-[84px]">
              <CustomDropdown<number>
                value={pageSize}
                onChange={(val) => {
                  setPageSize(Number(val));
                  setCurrentPage(1);
                }}
                options={[
                  { value: 10, label: '10' },
                  { value: 20, label: '20' },
                  { value: 50, label: '50' },
                ]}
                size="sm"
                triggerClassName="h-[32px] px-2.5 text-xs"
              />
            </div>
          </div>

          {/* View Toggle */}
          <div className="bg-slate-100 p-0.5 rounded-lg border border-slate-200/80 flex items-center">
            <button
              onClick={() => setViewMode('grid')}
              title="Grid Card View"
              className={`p-1.5 rounded-md transition-all cursor-pointer ${
                viewMode === 'grid'
                  ? 'bg-white text-[#0F766E] shadow-2xs font-semibold'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              title="Table View"
              className={`p-1.5 rounded-md transition-all cursor-pointer ${
                viewMode === 'table'
                  ? 'bg-white text-[#0F766E] shadow-2xs font-semibold'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* 4. Journal Content Grid / Table / Loading / Empty */}
      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-16 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 text-[#0F766E] animate-spin" />
          <p className="text-sm font-medium text-slate-600">Loading academic journals catalog...</p>
        </div>
      ) : error ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-8 text-center space-y-3">
          <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
          <h3 className="text-base font-bold text-rose-900">Unable to load journals</h3>
          <p className="text-sm text-rose-700 max-w-md mx-auto">{error}</p>
          <Button variant="secondary" size="sm" onClick={fetchJournals}>
            Try Again
          </Button>
        </div>
      ) : activeItems.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-[#14283D]">
              {filterShortlistedOnly ? 'No shortlisted journals found' : 'No journals found'}
            </h3>
            <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
              {filterShortlistedOnly
                ? totalShortlistedCount === 0
                  ? 'You have not shortlisted any journals yet. Click the bookmark icon on any journal card or table row to add it to your shortlist.'
                  : 'No shortlisted journals match your current search and filter combination.'
                : 'No academic venues match your current search and filter combination. Try clearing keywords or widening the selected subject area.'}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={handleResetFilters}>
            Clear All Filters
          </Button>
        </div>
      ) : viewMode === 'grid' ? (
        /* GRID VIEW */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {activeItems.map((journal) => {
            const shortlisted = isJournalShortlisted(journal.id);
            const compared = isJournalCompared(journal.id);

            return (
              <div
                key={journal.id}
                className="bg-white rounded-2xl border border-slate-200 hover:border-slate-300 hover:shadow-md transition-all p-5 flex flex-col justify-between group"
              >
                {/* Top Section */}
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-md bg-slate-100 text-slate-700">
                          {journal.publisher}
                        </span>
                        {journal.quartile && (
                          <span
                            className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${
                              journal.quartile === 'Q1'
                                ? 'bg-[#CCFBF1] text-[#0F766E]'
                                : journal.quartile === 'Q2'
                                ? 'bg-sky-50 text-sky-700'
                                : 'bg-slate-100 text-slate-600'
                            }`}
                          >
                            {journal.quartile}
                          </span>
                        )}
                        {journal.openAccessType && (
                          <span className="text-[11px] font-medium text-slate-500">
                            · {journal.openAccessType}
                          </span>
                        )}
                      </div>

                      <h3
                        onClick={() => setSelectedModalJournal(journal)}
                        className="text-base font-bold text-[#14283D] group-hover:text-[#0F766E] transition-colors cursor-pointer leading-snug pt-1"
                      >
                        {journal.title}
                      </h3>
                    </div>

                    {/* Bookmark action */}
                    <button
                      onClick={() => toggleShortlistJournal(journal.id, journal)}
                      title={shortlisted ? 'Remove from shortlist' : 'Add to shortlist'}
                      className={`p-2 rounded-xl transition-all cursor-pointer shrink-0 ${
                        shortlisted
                          ? 'bg-[#CCFBF1] text-[#0F766E]'
                          : 'text-slate-300 hover:text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {shortlisted ? (
                        <BookmarkCheck className="w-5 h-5" />
                      ) : (
                        <Bookmark className="w-5 h-5" />
                      )}
                    </button>
                  </div>

                  {/* Subject and ISSN */}
                  <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap">
                    {journal.subjectCategory && (
                      <span className="inline-flex items-center gap-1 text-slate-600 font-medium">
                        <FileText className="w-3.5 h-3.5 text-slate-400" />
                        {journal.subjectCategory}
                      </span>
                    )}
                    {journal.issn && (
                      <span className="inline-flex items-center gap-1 text-slate-400 font-mono text-[11px]">
                        ISSN: {journal.issn}
                      </span>
                    )}
                  </div>

                  {/* Aims and scope snippet */}
                  <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed whitespace-pre-line">
                    {journal.aimsAndScope?.replace(/\\n/g, '\n')}
                  </p>
                </div>

                {/* Bottom Metrics & Actions */}
                <div className="pt-4 mt-4 border-t border-slate-100 space-y-3">
                  <div className="grid grid-cols-4 gap-2 text-center bg-slate-50/70 p-2.5 rounded-xl border border-slate-100">
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">CiteScore</div>
                      <div className="text-xs sm:text-sm font-bold text-slate-800">
                        {journal.citeScore !== null && journal.citeScore !== undefined
                          ? journal.citeScore.toFixed(1)
                          : 'N/A'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Impact Factor</div>
                      <div className="text-xs sm:text-sm font-bold text-slate-800">
                        {journal.impactFactor !== null && journal.impactFactor !== undefined
                          ? journal.impactFactor.toFixed(1)
                          : 'N/A'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">First Decision</div>
                      <div className="text-xs sm:text-sm font-bold text-slate-800">
                        {journal.reviewWeeks !== null && journal.reviewWeeks !== undefined
                          ? `~${journal.reviewWeeks} w`
                          : 'N/A'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Acceptance</div>
                      <div className="text-xs sm:text-sm font-bold text-slate-800">
                        {journal.acceptanceRate !== null && journal.acceptanceRate !== undefined
                          ? `${journal.acceptanceRate}%`
                          : 'N/A'}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <button
                      onClick={() => setSelectedModalJournal(journal)}
                      className="text-xs font-semibold text-[#0F766E] hover:underline cursor-pointer flex items-center gap-1"
                    >
                      <Info className="w-3.5 h-3.5" />
                      View Full Scope
                    </button>

                    <button
                      onClick={() => toggleCompareJournal(journal.id)}
                      className={`text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors cursor-pointer flex items-center gap-1 ${
                        compared
                          ? 'bg-slate-800 text-white border-slate-800'
                          : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      <Columns2 className="w-3.5 h-3.5" />
                      {compared ? 'In Comparison' : 'Compare'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* TABLE VIEW */
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 border-b border-slate-200 text-[11px] uppercase font-bold text-slate-500 tracking-wider">
                <tr>
                  <th className="py-3 px-4">Journal Title</th>
                  <th className="py-3 px-3">Publisher</th>
                  <th className="py-3 px-3">Category</th>
                  <th className="py-3 px-3 text-center">Quartile</th>
                  <th className="py-3 px-3 text-right">CiteScore</th>
                  <th className="py-3 px-3 text-right">Impact Factor</th>
                  <th className="py-3 px-3 text-center">Time to First Decision</th>
                  <th className="py-3 px-3 text-center">Acceptance</th>
                  <th className="py-3 px-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {activeItems.map((journal) => {
                  const shortlisted = isJournalShortlisted(journal.id);
                  const compared = isJournalCompared(journal.id);

                  return (
                    <tr
                      key={journal.id}
                      className="hover:bg-slate-50/80 transition-colors group cursor-pointer"
                      onClick={() => setSelectedModalJournal(journal)}
                    >
                      <td className="py-3 px-4 font-semibold text-slate-900 group-hover:text-[#0F766E] transition-colors max-w-xs">
                        <div className="truncate">{journal.title}</div>
                        {journal.issn && (
                          <div className="text-[10px] text-slate-400 font-mono">ISSN: {journal.issn}</div>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                          {journal.publisher}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-600 truncate max-w-[160px]">
                        {journal.subjectCategory || '—'}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {journal.quartile ? (
                          <span
                            className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${
                              journal.quartile === 'Q1'
                                ? 'bg-[#CCFBF1] text-[#0F766E]'
                                : 'bg-slate-100 text-slate-600'
                            }`}
                          >
                            {journal.quartile}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-3 px-3 text-right font-semibold text-slate-800">
                        {journal.citeScore !== null && journal.citeScore !== undefined
                          ? journal.citeScore.toFixed(1)
                          : '—'}
                      </td>
                      <td className="py-3 px-3 text-right font-semibold text-slate-800">
                        {journal.impactFactor !== null && journal.impactFactor !== undefined
                          ? journal.impactFactor.toFixed(1)
                          : '—'}
                      </td>
                      <td className="py-3 px-3 text-center text-slate-600">
                        {journal.reviewWeeks ? `~${journal.reviewWeeks} w` : '—'}
                      </td>
                      <td className="py-3 px-3 text-center text-slate-600">
                        {journal.acceptanceRate ? `${journal.acceptanceRate}%` : '—'}
                      </td>
                      <td
                        className="py-3 px-4 text-center"
                        onClick={(e) => e.stopPropagation()} // Prevent opening modal on action click
                      >
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            onClick={() => toggleShortlistJournal(journal.id, journal)}
                            title={shortlisted ? 'Remove shortlist' : 'Add to shortlist'}
                            className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                              shortlisted
                                ? 'bg-[#CCFBF1] text-[#0F766E]'
                                : 'text-slate-400 hover:text-slate-700 hover:bg-slate-100'
                            }`}
                          >
                            {shortlisted ? (
                              <BookmarkCheck className="w-4 h-4" />
                            ) : (
                              <Bookmark className="w-4 h-4" />
                            )}
                          </button>
                          <button
                            onClick={() => toggleCompareJournal(journal.id)}
                            title={compared ? 'In comparison' : 'Add to compare'}
                            className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                              compared
                                ? 'bg-slate-800 text-white'
                                : 'text-slate-400 hover:text-slate-700 hover:bg-slate-100'
                            }`}
                          >
                            <Columns2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. Pagination Bar */}
      {activeTotalPages > 1 && (
        <div className="bg-white rounded-2xl border border-slate-200/90 px-4 py-3 flex items-center justify-between gap-2 shadow-xs">
          <Button
            variant="secondary"
            size="sm"
            disabled={currentPage <= 1 || (loading && !filterShortlistedOnly)}
            onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
            leftIcon={<ChevronLeft className="w-4 h-4" />}
          >
            Previous
          </Button>

          <div className="flex items-center gap-1">
            {Array.from({ length: activeTotalPages }, (_, i) => i + 1).map((pageNum) => {
              // Show pages around current
              if (
                pageNum === 1 ||
                pageNum === activeTotalPages ||
                Math.abs(pageNum - currentPage) <= 1
              ) {
                return (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={`w-8 h-8 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                      currentPage === pageNum
                        ? 'bg-[#0F766E] text-white shadow-xs'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              }
              if (
                pageNum === currentPage - 2 ||
                pageNum === currentPage + 2
              ) {
                return (
                  <span key={pageNum} className="text-slate-400 px-1 text-xs">
                    …
                  </span>
                );
              }
              return null;
            })}
          </div>

          <Button
            variant="secondary"
            size="sm"
            disabled={currentPage >= activeTotalPages || (loading && !filterShortlistedOnly)}
            onClick={() => setCurrentPage((prev) => Math.min(activeTotalPages, prev + 1))}
            rightIcon={<ChevronRight className="w-4 h-4" />}
          >
            Next
          </Button>
        </div>
      )}

      {/* 6. Journal Scope Details Modal */}
      {selectedModalJournal && (
        <div
          className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4"
          onClick={() => setSelectedModalJournal(null)}
        >
          <div
            className="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-100 flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-md bg-slate-100 text-slate-700">
                    {selectedModalJournal.publisher}
                  </span>
                  {selectedModalJournal.quartile && (
                    <span className="text-xs font-bold px-2.5 py-0.5 rounded-md bg-[#CCFBF1] text-[#0F766E]">
                      {selectedModalJournal.quartile}
                    </span>
                  )}
                  {selectedModalJournal.openAccessType && (
                    <span className="text-xs font-medium text-slate-500">
                      · {selectedModalJournal.openAccessType}
                    </span>
                  )}
                </div>
                <h2 className="text-xl font-bold text-[#14283D] pt-1">
                  {selectedModalJournal.title}
                </h2>
                {selectedModalJournal.subjectCategory && (
                  <p className="text-xs text-slate-500 font-medium">
                    Field: {selectedModalJournal.subjectCategory}
                  </p>
                )}
              </div>

              <button
                onClick={() => setSelectedModalJournal(null)}
                className="w-8 h-8 rounded-full bg-slate-100 text-slate-500 hover:bg-slate-200 hover:text-slate-800 flex items-center justify-center transition-colors cursor-pointer shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6">
              {/* Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-[11px] font-bold text-slate-400 uppercase">CiteScore</div>
                  <div className="text-base font-extrabold text-slate-900 mt-0.5">
                    {selectedModalJournal.citeScore !== null && selectedModalJournal.citeScore !== undefined
                      ? selectedModalJournal.citeScore.toFixed(1)
                      : 'N/A'}
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-[11px] font-bold text-slate-400 uppercase">Impact Factor</div>
                  <div className="text-base font-extrabold text-slate-900 mt-0.5">
                    {selectedModalJournal.impactFactor !== null && selectedModalJournal.impactFactor !== undefined
                      ? selectedModalJournal.impactFactor.toFixed(1)
                      : 'N/A'}
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-[11px] font-bold text-slate-400 uppercase">Time to First Decision</div>
                  <div className="text-base font-extrabold text-slate-900 mt-0.5">
                    {selectedModalJournal.reviewWeeks
                      ? `~${selectedModalJournal.reviewWeeks} weeks`
                      : 'N/A'}
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-[11px] font-bold text-slate-400 uppercase">Acceptance Rate</div>
                  <div className="text-base font-extrabold text-slate-900 mt-0.5">
                    {selectedModalJournal.acceptanceRate
                      ? `${selectedModalJournal.acceptanceRate}%`
                      : 'N/A'}
                  </div>
                </div>
              </div>

              {/* Aims and Scope Section */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <BookOpen className="w-4 h-4 text-[#0F766E]" />
                    Official Aims & Scope
                  </h4>
                  <button
                    onClick={() => handleCopyScope(selectedModalJournal.aimsAndScope?.replace(/\\n/g, '\n'))}
                    className="text-xs text-[#0F766E] hover:underline cursor-pointer flex items-center gap-1 font-medium"
                  >
                    {copiedScope ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        Copied!
                      </>
                    ) : (
                      'Copy Text'
                    )}
                  </button>
                </div>
                <div className="bg-slate-50/90 rounded-2xl p-4 border border-slate-200/80 text-sm text-slate-700 leading-relaxed max-h-64 overflow-y-auto whitespace-pre-line">
                  {selectedModalJournal.aimsAndScope?.replace(/\\n/g, '\n')}
                </div>
              </div>

              {/* Publication metadata */}
              <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100">
                <span className="font-mono">ISSN: {selectedModalJournal.issn || 'Not available'}</span>
                <span>Access: {selectedModalJournal.openAccessType || 'Standard'}</span>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-5 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Button
                  variant={isJournalShortlisted(selectedModalJournal.id) ? 'mint' : 'secondary'}
                  size="sm"
                  onClick={() => toggleShortlistJournal(selectedModalJournal.id, selectedModalJournal)}
                  leftIcon={
                    isJournalShortlisted(selectedModalJournal.id) ? (
                      <BookmarkCheck className="w-4 h-4" />
                    ) : (
                      <Bookmark className="w-4 h-4" />
                    )
                  }
                >
                  {isJournalShortlisted(selectedModalJournal.id)
                    ? 'Shortlisted'
                    : 'Add to Shortlist'}
                </Button>

                <Button
                  variant={isJournalCompared(selectedModalJournal.id) ? 'primary' : 'outline'}
                  size="sm"
                  onClick={() => toggleCompareJournal(selectedModalJournal.id)}
                  leftIcon={<Columns2 className="w-4 h-4" />}
                >
                  {isJournalCompared(selectedModalJournal.id) ? 'In Compare' : 'Compare'}
                </Button>
              </div>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedModalJournal(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
