import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Bookmark,
  BookmarkCheck,
  UploadCloud,
  FileText,
  Info,
  Loader2,
  Check,
  Columns2,
  AlertCircle,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/StatusBadge';

export const JournalFinderPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    activeProject,
    journals,
    toggleShortlistJournal,
    selectedCompareJournalIds,
    toggleCompareJournal,
  } = useApp();

  const [activeTab, setActiveTab] = useState<'paste' | 'upload'>('paste');
  const [title, setTitle] = useState(
    activeProject?.title || 'Urban green infrastructure and heat resilience'
  );
  const [abstract, setAbstract] = useState(
    activeProject?.abstract ||
      'We evaluate how urban green infrastructure influences neighborhood heat exposure across 24 cities. Using satellite-derived land surface temperatures and a longitudinal panel model, we find that connected green spaces reduce peak summer temperatures, with the largest benefits in densely built neighborhoods.'
  );
  const [keywords, setKeywords] = useState(
    activeProject?.keywords?.join(', ') || 'urban heat, green infrastructure, resilience'
  );
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  // States: 'idle' | 'loading' | 'results' | 'error'
  const [searchState, setSearchState] = useState<'idle' | 'loading' | 'results'>('results');
  const [activeFilter, setActiveFilter] = useState<'all' | 'environmental' | 'open_access'>('all');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() && !abstract.trim() && !uploadedFile) {
      alert('Please provide a paper title, abstract, or upload a manuscript.');
      return;
    }
    setSearchState('loading');
    setTimeout(() => {
      setSearchState('results');
    }, 900);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setUploadedFile(file);
      setTitle(file.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' '));
    }
  };

  const shortlistedCount = journals.filter((j) => j.isShortlisted).length;

  const filteredJournals = journals.filter((j) => {
    if (activeFilter === 'environmental') {
      return j.subjectCategory.toLowerCase().includes('environmental');
    }
    if (activeFilter === 'open_access') {
      return j.openAccessType === 'Open access';
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
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Paper title
              </label>
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
                placeholder="e.g. urban climate, sustainability, satellite data"
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

            <Button
              type="submit"
              size="md"
              isLoading={searchState === 'loading'}
              className="w-full h-[44px] shadow-sm mt-3"
              leftIcon={<Search className="w-4 h-4" />}
            >
              {searchState === 'loading' ? 'Searching Scopes...' : 'Find Journals'}
            </Button>
          </form>

          <p className="text-[11px] text-center text-slate-400 pt-1">
            Your manuscript stays private. You're in control of what you share.
          </p>
        </div>

        {/* Right Column (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
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
                  Add a title and abstract, or upload a paper to discover relevant journals based on semantic similarity.
                </p>
                <span className="mt-4 px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
                  No search yet
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
                  Computing SPECTER semantic embeddings and ranking journals across Scopus and Web of Science.
                </p>
              </div>
            </div>
          )}

          {searchState === 'results' && (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <h2 className="text-base font-bold text-[#14283D]">Recommended journals</h2>
                <span className="text-xs text-slate-500 font-medium">
                  {filteredJournals.length} matches · Best fit first
                </span>
              </div>

              {/* Filters */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                <button
                  onClick={() => setActiveFilter('all')}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                    activeFilter === 'all'
                      ? 'bg-[#0F766E] text-white shadow-2xs'
                      : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  All journals
                </button>
                <button
                  onClick={() => setActiveFilter('environmental')}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                    activeFilter === 'environmental'
                      ? 'bg-[#0F766E] text-white shadow-2xs'
                      : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  Environmental science
                </button>
                <button
                  onClick={() => setActiveFilter('open_access')}
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
                {filteredJournals.map((journal) => {
                  const isCompared = selectedCompareJournalIds.includes(journal.id);
                  return (
                    <div
                      key={journal.id}
                      className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs hover:border-slate-300 transition-all space-y-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3.5">
                          {/* Circular match badge */}
                          <div className="w-13 h-13 rounded-full border-2 border-[#0F766E] bg-[#CCFBF1]/30 flex flex-col items-center justify-center shrink-0">
                            <span className="text-xs font-extrabold text-[#0F766E] leading-none">
                              {journal.matchScore}%
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
                              <StatusBadge status={journal.quartile} />
                              <StatusBadge status={journal.openAccessType} />
                            </div>
                          </div>
                        </div>

                        {/* Bookmark Button */}
                        <button
                          onClick={() => toggleShortlistJournal(journal.id)}
                          title={journal.isShortlisted ? 'Remove from shortlist' : 'Add to shortlist'}
                          className={`p-2 rounded-xl transition-colors cursor-pointer ${
                            journal.isShortlisted
                              ? 'text-[#0F766E] bg-[#CCFBF1]'
                              : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100'
                          }`}
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
                          CiteScore <span className="font-semibold text-slate-700">{journal.citeScore}</span> · Review <span className="font-semibold text-slate-700">{journal.reviewWeeks} weeks</span> · Acceptance <span className="font-semibold text-slate-700">{journal.acceptanceRate}%</span>
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
                            variant={journal.isShortlisted ? 'primary' : 'secondary'}
                            onClick={() => toggleShortlistJournal(journal.id)}
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
                })}
              </div>

              <p className="text-[11px] text-center text-slate-400 pt-2">
                Illustrative journal profiles and metrics for demonstration; verify details before submission.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
