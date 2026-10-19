import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Bookmark,
  BookmarkCheck,
  UploadCloud,
  Info,
  Loader2,
  Check,
  Columns2,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/StatusBadge';
import { Journal } from '../types';
import { matchJournals, createProject, shortlistJournal, unshortlistJournal } from '../lib/api';

/**
 * Formats numeric metrics safely. Returns "N/A" for null/undefined values without any unit suffix.
 */
function formatMetric(val: number | null | undefined, unit = ''): string {
  if (val == null) return 'N/A';
  return `${val}${unit ? ` ${unit}` : ''}`;
}

export const JournalFinderPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    activeProject,
    setActiveProject,
    journals,
    mergeJournals,
    setJournalShortlisted,
    selectedCompareJournalIds,
    toggleCompareJournal,
  } = useApp();

  const [activeTab, setActiveTab] = useState<'paste' | 'upload'>('paste');

  // Input states start empty per plan specification (ignoring mock urban-heat project from initial data)
  const isMockDemoProject =
    activeProject?.id === 'proj_01' ||
    activeProject?.title?.toLowerCase().includes('urban green');

  const [title, setTitle] = useState(!isMockDemoProject ? activeProject?.title || '' : '');
  const [abstract, setAbstract] = useState(!isMockDemoProject ? activeProject?.abstract || '' : '');
  const [keywords, setKeywords] = useState(
    !isMockDemoProject ? activeProject?.keywords?.join(', ') || '' : ''
  );
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  const loadSamplePaper = () => {
    setTitle('Deep Residual Learning for Image Recognition');
    setAbstract(
      'Deeper neural networks are more difficult to train. We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously. We explicitly reformulate the layers as learning residual functions with reference to the layer inputs, instead of learning unreferenced functions. Comprehensive empirical evidence shows that these residual networks are easier to optimize and gain accuracy from considerably increased depth.'
    );
    setKeywords('deep learning, neural networks, computer vision, residual representations');
    setValidationError(null);
  };

  const handleClearForm = () => {
    setTitle('');
    setAbstract('');
    setKeywords('');
    setUploadedFile(null);
    setValidationError(null);
  };

  // Search execution states: 'idle' | 'loading' | 'results' | 'error'
  const [searchState, setSearchState] = useState<'idle' | 'loading' | 'results' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [notificationMessage, setNotificationMessage] = useState<string | null>(null);

  const [matchedJournals, setMatchedJournals] = useState<Journal[]>([]);
  const [metaInfo, setMetaInfo] = useState<{ tookMs: number; totalJournals: number; model: string } | null>(null);

  // Filter state
  const [activeFilter, setActiveFilter] = useState<string>('all');

  // Shortlisting concurrency guards
  const [inFlightShortlistIds, setInFlightShortlistIds] = useState<Set<string>>(new Set());
  const creatingProjectRef = useRef<boolean>(false);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setValidationError(null);
    setErrorMessage(null);
    setNotificationMessage(null);

    const cleanTitle = title.trim();
    const cleanAbstract = abstract.trim();

    // Check if user uploaded a file without title and abstract
    if (!cleanTitle && !cleanAbstract) {
      if (uploadedFile) {
        setValidationError(
          'Manuscript file uploaded. Automated file extraction is coming soon; please paste your title and abstract to find matching journals.'
        );
      } else {
        setValidationError('Please provide a manuscript title or abstract to find matching journals.');
      }
      return;
    }

    const kwList = keywords
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean);

    setSearchState('loading');

    try {
      const resp = await matchJournals({
        title: cleanTitle || undefined,
        abstract: cleanAbstract || undefined,
        keywords: kwList.length > 0 ? kwList : undefined,
        projectId: activeProject?.id,
        limit: 20,
      });

      setMatchedJournals(resp.results);
      mergeJournals(resp.results);
      setMetaInfo(resp.meta);
      setSearchState('results');
    } catch (err: any) {
      setErrorMessage(
        err.message || 'Failed to search matching journals. Please check your connection and try again.'
      );
      setSearchState('error');
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setUploadedFile(file);
      setTitle(file.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' '));
      setValidationError(null);
    }
  };

  const handleToggleShortlist = async (journal: Journal) => {
    if (inFlightShortlistIds.has(journal.id)) return;

    setValidationError(null);
    setNotificationMessage(null);

    const isCurrentlyShortlisted = !!journal.isShortlisted;
    const newShortlistedState = !isCurrentlyShortlisted;

    // Optimistically update card & context state
    setMatchedJournals((prev) =>
      prev.map((j) => (j.id === journal.id ? { ...j, isShortlisted: newShortlistedState } : j))
    );
    setJournalShortlisted(journal.id, newShortlistedState);
    setInFlightShortlistIds((prev) => new Set(prev).add(journal.id));

    try {
      let targetProjectId = activeProject?.id;

      // Auto-project rule: if there is no active project, auto-create one
      if (!targetProjectId) {
        if (creatingProjectRef.current) {
          return;
        }
        creatingProjectRef.current = true;

        const cleanTitle = title.trim();
        const cleanAbstract = abstract.trim();

        // Derivation rule: if title is empty, derive from the first 7 words of abstract
        let projectTitle = cleanTitle;
        if (!projectTitle && cleanAbstract) {
          projectTitle = cleanAbstract.split(/\s+/).slice(0, 7).join(' ') + '...';
        }

        if (!projectTitle) {
          throw new Error('Please enter a title or abstract before shortlisting to assign to a project.');
        }

        const kwList = keywords
          .split(',')
          .map((k) => k.trim())
          .filter(Boolean);

        const newProj = await createProject({
          title: projectTitle,
          abstract: cleanAbstract,
          keywords: kwList,
        });

        setActiveProject(newProj);
        targetProjectId = newProj.id;
        setNotificationMessage(`Created project "${newProj.title}" and shortlisted journal.`);
        creatingProjectRef.current = false;
      }

      if (newShortlistedState) {
        await shortlistJournal(targetProjectId, journal.id, journal.rawSimilarity ?? undefined);
        if (!notificationMessage) {
          setNotificationMessage(`Added "${journal.title}" to shortlist.`);
        }
      } else {
        await unshortlistJournal(targetProjectId, journal.id);
        setNotificationMessage(`Removed "${journal.title}" from shortlist.`);
      }
    } catch (err: any) {
      // Rollback optimistic update
      setMatchedJournals((prev) =>
        prev.map((j) => (j.id === journal.id ? { ...j, isShortlisted: isCurrentlyShortlisted } : j))
      );
      setJournalShortlisted(journal.id, isCurrentlyShortlisted);
      setValidationError(err.message || 'Failed to update shortlist.');
    } finally {
      creatingProjectRef.current = false;
      setInFlightShortlistIds((prev) => {
        const next = new Set(prev);
        next.delete(journal.id);
        return next;
      });
    }
  };

  const shortlistedCount = journals.filter((j) => j.isShortlisted).length;

  // Extract distinct publishers from real matching results
  const availablePublishers = React.useMemo(() => {
    const pubSet = new Set<string>();
    matchedJournals.forEach((j) => {
      if (j.publisher) pubSet.add(j.publisher);
    });
    return Array.from(pubSet).slice(0, 5);
  }, [matchedJournals]);

  // Client-side filtering
  const filteredJournals = matchedJournals.filter((j) => {
    if (activeFilter === 'open_access') {
      return j.openAccessType === 'Open access';
    }
    if (activeFilter === 'q1') {
      return j.quartile === 'Q1';
    }
    if (activeFilter.startsWith('pub:')) {
      const pubName = activeFilter.slice(4);
      return j.publisher === pubName;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
            Find the right home for your research.
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Discover journals that align with your manuscript, not just your keywords.
          </p>
        </div>

        <Button
          variant="secondary"
          onClick={() => navigate('/compare')}
          leftIcon={<Bookmark className="w-4 h-4 text-[#0F766E]" />}
          className="shadow-2xs self-start sm:self-auto"
        >
          My shortlist · {shortlistedCount}
        </Button>
      </div>

      {/* Main Grid: Form on Left, Output on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h2 className="text-base font-bold text-[#14283D]">Tell us about your paper</h2>
            <div className="flex items-center gap-2 text-xs font-medium">
              <button
                type="button"
                onClick={() => setActiveTab('paste')}
                className={`pb-1 cursor-pointer transition-colors ${
                  activeTab === 'paste'
                    ? 'text-[#0F766E] border-b-2 border-[#0F766E] font-semibold'
                    : 'text-slate-400 hover:text-slate-600'
                }`}
              >
                Paste details
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('upload')}
                className={`pb-1 cursor-pointer transition-colors ${
                  activeTab === 'upload'
                    ? 'text-[#0F766E] border-b-2 border-[#0F766E] font-semibold'
                    : 'text-slate-400 hover:text-slate-600'
                }`}
              >
                Upload manuscript
              </button>
            </div>
          </div>

          <form onSubmit={handleSearch} className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Paper title
                </label>
                <div className="flex items-center gap-2.5">
                  {!title && !abstract && (
                    <button
                      type="button"
                      onClick={loadSamplePaper}
                      className="text-[11px] font-semibold text-[#0F766E] hover:underline cursor-pointer"
                    >
                      + Load CS sample
                    </button>
                  )}
                  {(title || abstract || keywords) && (
                    <button
                      type="button"
                      onClick={handleClearForm}
                      className="text-[11px] font-medium text-slate-400 hover:text-slate-600 cursor-pointer"
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter your manuscript title"
                className="w-full px-3.5 h-[40px] rounded-xl border border-slate-200 text-sm focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Abstract
              </label>
              <textarea
                rows={5}
                value={abstract}
                onChange={(e) => setAbstract(e.target.value)}
                placeholder="Paste your abstract here..."
                className="w-full p-3.5 rounded-xl border border-slate-200 text-sm focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none transition-all resize-none leading-relaxed"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Keywords
              </label>
              <input
                type="text"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="e.g. machine learning, computer vision, optimization"
                className="w-full px-3.5 h-[40px] rounded-xl border border-slate-200 text-sm focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none transition-all"
              />
            </div>

            {/* Upload Zone */}
            <div className="pt-2">
              <div className="text-center text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                OR UPLOAD YOUR PAPER
              </div>
              <label className="border-2 border-dashed border-slate-200 hover:border-[#0F766E]/50 rounded-2xl p-5 flex flex-col items-center justify-center bg-slate-50/50 hover:bg-[#CCFBF1]/20 cursor-pointer transition-all">
                <UploadCloud className="w-8 h-8 text-[#0F766E] mb-2 stroke-[1.5]" />
                <p className="text-sm font-semibold text-slate-800">
                  {uploadedFile ? uploadedFile.name : 'Drop a paper or browse files'}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  PDF or DOCX · up to 20 MB
                </p>
                <input
                  type="file"
                  accept=".docx,.pdf,.tex"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>

            {/* Validation Message Box */}
            {validationError && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-2.5 text-xs text-amber-800">
                <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                <span className="leading-snug">{validationError}</span>
              </div>
            )}

            <Button
              type="submit"
              size="md"
              isLoading={searchState === 'loading'}
              className="w-full h-[44px] shadow-sm mt-3"
              leftIcon={<Search className="w-4 h-4" />}
            >
              {searchState === 'loading' ? 'Searching Catalog Scopes...' : 'Find Journals'}
            </Button>
          </form>

          <p className="text-[11px] text-center text-slate-400 pt-1">
            Your manuscript stays private. You're in control of what you share.
          </p>
        </div>

        {/* Right Column (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Notification alert */}
          {notificationMessage && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs text-emerald-800">
              <span className="font-medium">{notificationMessage}</span>
              <button
                type="button"
                onClick={() => setNotificationMessage(null)}
                className="text-emerald-600 hover:text-emerald-900 font-bold ml-2 cursor-pointer"
              >
                ×
              </button>
            </div>
          )}

          {searchState === 'idle' && (
            <div className="space-y-4">
              <h2 className="text-base font-bold text-[#14283D]">Your journal matches</h2>
              <div className="bg-white rounded-2xl p-12 border border-slate-200/80 shadow-2xs flex flex-col items-center justify-center text-center min-h-[380px]">
                <div className="w-16 h-16 rounded-full bg-[#CCFBF1] text-[#0F766E] flex items-center justify-center mb-4">
                  <Search className="w-8 h-8 stroke-[1.75]" />
                </div>
                <h3 className="text-lg font-bold text-[#14283D]">
                  Your next journal starts here
                </h3>
                <p className="text-xs sm:text-sm text-slate-500 max-w-sm mt-1.5 leading-relaxed">
                  Add a title and abstract, or paste your abstract to discover relevant journals based on semantic similarity.
                </p>
                <span className="mt-4 px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
                  Ready to search
                </span>
              </div>

              <div className="p-3.5 bg-[#F0FDF4] border border-[#DCFCE7] rounded-xl flex items-center gap-2.5 text-xs text-[#166534]">
                <Info className="w-4 h-4 shrink-0 text-[#16A34A]" />
                <span>Tip: a clear abstract and specific keywords help surface more relevant journals.</span>
              </div>
            </div>
          )}

          {searchState === 'loading' && (
            <div className="space-y-4">
              <h2 className="text-base font-bold text-[#14283D]">Your journal matches</h2>
              <div className="bg-white rounded-2xl p-12 border border-slate-200/80 shadow-2xs flex flex-col items-center justify-center text-center min-h-[380px]">
                <Loader2 className="w-10 h-10 text-[#0F766E] animate-spin mb-3" />
                <h3 className="text-base font-bold text-[#14283D]">
                  Analyzing manuscript against indexed scopes...
                </h3>
                <p className="text-xs text-slate-500 max-w-sm mt-1">
                  Computing SPECTER semantic embeddings and ranking journals across our curated catalog.
                </p>
              </div>
            </div>
          )}

          {searchState === 'error' && (
            <div className="space-y-4">
              <h2 className="text-base font-bold text-[#14283D]">Your journal matches</h2>
              <div className="bg-white rounded-2xl p-12 border border-red-200/80 shadow-2xs flex flex-col items-center justify-center text-center min-h-[380px] space-y-4">
                <div className="w-14 h-14 rounded-full bg-red-50 text-red-600 flex items-center justify-center">
                  <AlertCircle className="w-8 h-8 stroke-[1.75]" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Search Failed</h3>
                  <p className="text-xs text-slate-500 max-w-md mt-1 leading-relaxed">
                    {errorMessage || 'An error occurred while matching your manuscript. Please try again.'}
                  </p>
                </div>
                <Button
                  size="md"
                  variant="primary"
                  onClick={() => handleSearch()}
                  leftIcon={<RefreshCw className="w-4 h-4" />}
                >
                  Retry Search
                </Button>
              </div>
            </div>
          )}

          {searchState === 'results' && (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <h2 className="text-base font-bold text-[#14283D]">Recommended journals</h2>
                <span className="text-xs text-slate-500 font-medium">
                  {filteredJournals.length} matches
                  {metaInfo ? ` · ${metaInfo.tookMs}ms` : ''} · Best fit first
                </span>
              </div>

              {/* Dynamic Filters */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                <button
                  type="button"
                  onClick={() => setActiveFilter('all')}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                    activeFilter === 'all'
                      ? 'bg-[#0F766E] text-white shadow-2xs'
                      : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  All journals ({matchedJournals.length})
                </button>

                {availablePublishers.map((pub) => (
                  <button
                    key={pub}
                    type="button"
                    onClick={() => setActiveFilter(activeFilter === `pub:${pub}` ? 'all' : `pub:${pub}`)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                      activeFilter === `pub:${pub}`
                        ? 'bg-[#0F766E] text-white shadow-2xs'
                        : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {pub}
                  </button>
                ))}

                <button
                  type="button"
                  onClick={() => setActiveFilter(activeFilter === 'q1' ? 'all' : 'q1')}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                    activeFilter === 'q1'
                      ? 'bg-[#0F766E] text-white shadow-2xs'
                      : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  Q1 Only
                </button>

                <button
                  type="button"
                  onClick={() => setActiveFilter(activeFilter === 'open_access' ? 'all' : 'open_access')}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                    activeFilter === 'open_access'
                      ? 'bg-[#0F766E] text-white shadow-2xs'
                      : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  Open access
                </button>
              </div>

              {/* Journal Cards */}
              <div className="space-y-3.5">
                {filteredJournals.length === 0 ? (
                  <div className="bg-white rounded-2xl p-8 border border-slate-200/80 text-center text-slate-500 text-sm">
                    No journals match the selected filter.
                  </div>
                ) : (
                  filteredJournals.map((journal) => {
                    const isCompared = selectedCompareJournalIds.includes(journal.id);
                    const isInFlight = inFlightShortlistIds.has(journal.id);

                    return (
                      <div
                        key={journal.id}
                        className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs hover:border-slate-300 transition-all space-y-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3.5">
                            {/* Circular match badge */}
                            <div
                              className="w-13 h-13 rounded-full border-2 border-[#0F766E] bg-[#CCFBF1]/30 flex flex-col items-center justify-center shrink-0"
                              title={
                                journal.rawSimilarity != null
                                  ? `SPECTER Cosine Similarity: ${journal.rawSimilarity.toFixed(4)}`
                                  : undefined
                              }
                            >
                              <span className="text-xs font-extrabold text-[#0F766E] leading-none">
                                {journal.matchScore != null ? `${journal.matchScore}%` : '—'}
                              </span>
                              <span className="text-[9px] font-bold uppercase tracking-wider text-teal-700 mt-0.5">
                                MATCH
                              </span>
                            </div>

                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-bold text-base text-[#14283D] leading-snug">
                                  {journal.title}
                                </h3>
                                {journal.matchTag && (
                                  <span className="bg-[#CCFBF1] text-[#0F766E] text-[10px] font-bold px-2 py-0.5 rounded-full border border-[#99F6E4]">
                                    {journal.matchTag}
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-slate-400 mt-0.5">
                                {journal.publisher} · {journal.subjectCategory}
                              </p>
                              <div className="flex items-center gap-2 mt-2">
                                <StatusBadge status={journal.quartile || 'Q1'} />
                                <StatusBadge status={journal.openAccessType || 'Hybrid'} />
                              </div>
                            </div>
                          </div>

                          {/* Bookmark Button */}
                          <button
                            type="button"
                            disabled={isInFlight}
                            onClick={() => handleToggleShortlist(journal)}
                            title={journal.isShortlisted ? 'Remove from shortlist' : 'Add to shortlist'}
                            className={`p-2 rounded-xl transition-colors cursor-pointer ${
                              journal.isShortlisted
                                ? 'text-[#0F766E] bg-[#CCFBF1]'
                                : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100'
                            } ${isInFlight ? 'opacity-50 cursor-not-allowed' : ''}`}
                          >
                            {journal.isShortlisted ? (
                              <BookmarkCheck className="w-4 h-4 fill-current stroke-[2]" />
                            ) : (
                              <Bookmark className="w-4 h-4" />
                            )}
                          </button>
                        </div>

                        {/* Scope snippet */}
                        <p className="text-xs text-slate-600 bg-slate-50/70 p-2.5 rounded-xl border border-slate-100 leading-relaxed">
                          {journal.aimsAndScope}
                        </p>

                        {/* Bottom Bar: Metrics & Actions */}
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1 border-t border-slate-100 text-xs text-slate-500">
                          <div>
                            CiteScore{' '}
                            <span className="font-semibold text-slate-700">
                              {formatMetric(journal.citeScore)}
                            </span>{' '}
                            · Review{' '}
                            <span className="font-semibold text-slate-700">
                              {formatMetric(journal.reviewWeeks, 'weeks')}
                            </span>{' '}
                            · Acceptance{' '}
                            <span className="font-semibold text-slate-700">
                              {formatMetric(journal.acceptanceRate, '%')}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              variant={isCompared ? 'mint' : 'secondary'}
                              onClick={() => toggleCompareJournal(journal.id)}
                              leftIcon={<Columns2 className="w-3.5 h-3.5" />}
                            >
                              {isCompared ? 'Comparing' : 'Compare'}
                            </Button>
                            <Button
                              size="sm"
                              disabled={isInFlight}
                              variant={journal.isShortlisted ? 'primary' : 'secondary'}
                              onClick={() => handleToggleShortlist(journal)}
                              leftIcon={
                                journal.isShortlisted ? (
                                  <Check className="w-3.5 h-3.5" />
                                ) : (
                                  <Bookmark className="w-3.5 h-3.5" />
                                )
                              }
                            >
                              {journal.isShortlisted ? 'Shortlisted' : 'Shortlist'}
                            </Button>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <p className="text-[11px] text-center text-slate-400 pt-2">
                Curated academic journal profiles and metrics; verify current guidelines before submission.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
