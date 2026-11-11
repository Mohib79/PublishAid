import React, { useState, useEffect, useRef } from 'react';
import {
  Building2,
  Sliders,
  FileText,
  Save,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  Download,
  CheckCircle2,
  FileCheck,
  Globe,
  Clipboard,
  AlertTriangle,
  Loader2,
  XCircle,
  Copy,
  Trash2,
  ExternalLink,
  Info,
  Check,
  RefreshCw,
  FolderGit2,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  HelpCircle,
  Clock,
  Layers,
  Link2
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import {
  createGuidelineExtraction,
  getGuidelineExtraction,
  cancelGuidelineExtraction,
  confirmGuidelineExtraction,
  getGuidelineExtractions,
  getGuidelineRuleSets,
  getGuidelineRuleSetVersions,
  activateGuidelineRuleSet,
  copyGuidelineRuleSet,
  deleteGuidelineRuleSet,
  retryGuidelineExtraction,
  deleteGuidelineExtraction,
  linkProjectGuidelineRule
} from '../lib/api';
import {
  GuidelineExtractionJob,
  GuidelineRuleSet,
  GuidelineExtractionDraft,
  GuidelineFieldProvenance,
  Project
} from '../types';

// Safe URL and Date parser helpers to prevent UI render crashes on malformed data
function safeHostname(raw?: string | null): string {
  if (!raw) return 'Pasted text';
  try {
    return new URL(raw).hostname;
  } catch {
    return raw.length > 30 ? `${raw.slice(0, 30)}...` : raw;
  }
}

function safeFormatDate(raw?: string | null): string {
  if (!raw) return '';
  try {
    const d = new Date(raw);
    return isNaN(d.getTime()) ? '' : d.toLocaleDateString();
  } catch {
    return '';
  }
}

export const GuidelinesTemplatesPage: React.FC = () => {
  const { projects, activeProject, setActiveProjectId, journals, addActivity } = useApp();

  // Primary page tabs
  const [activeTab, setActiveTab] = useState<'extract' | 'rulesets' | 'template'>('extract');

  // ==========================================
  // EXTRACTION WORKFLOW STATE
  // ==========================================
  const [extractionSubStep, setExtractionSubStep] = useState<'input' | 'processing' | 'review'>('input');
  const [inputMode, setInputMode] = useState<'url' | 'text'>('url');
  const [guidelinesUrl, setGuidelinesUrl] = useState('');
  const [guidelinesText, setGuidelinesText] = useState('');
  const [selectedJournalId, setSelectedJournalId] = useState<string>('');
  const [selectedProjectId, setSelectedProjectId] = useState<string>(activeProject?.id || '');

  // Live Job Polling
  const [currentJob, setCurrentJob] = useState<GuidelineExtractionJob | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [isStartingJob, setIsStartingJob] = useState(false);
  const pollingRef = useRef<any>(null);

  // Review & Edit State
  const [reviewRules, setReviewRules] = useState<Record<string, any>>({});
  const [reviewFields, setReviewFields] = useState<Record<string, GuidelineFieldProvenance>>({});
  const [reviewCategory, setReviewCategory] = useState<'documentStructure' | 'citations' | 'figuresAndTables' | 'submissionStyle'>('documentStructure');
  const [reviewedAllFlags, setReviewedAllFlags] = useState(false);
  const [ruleSetName, setRuleSetName] = useState('');
  const [isConfirming, setIsConfirming] = useState(false);
  const [reviewSuccessMsg, setReviewSuccessMsg] = useState<string | null>(null);

  // Recent Extractions
  const [recentExtractions, setRecentExtractions] = useState<GuidelineExtractionJob[]>([]);
  const [isLoadingRecents, setIsLoadingRecents] = useState(false);

  // ==========================================
  // RULE SETS LIBRARY STATE
  // ==========================================
  const [ruleSets, setRuleSets] = useState<GuidelineRuleSet[]>([]);
  const [isLoadingRuleSets, setIsLoadingRuleSets] = useState(false);
  const [ruleSetFilter, setRuleSetFilter] = useState<'all' | 'custom' | 'seed'>('all');
  const [selectedRuleSetForView, setSelectedRuleSetForView] = useState<GuidelineRuleSet | null>(null);
  const [versionHistory, setVersionHistory] = useState<GuidelineRuleSet[]>([]);
  const [linkingProjectId, setLinkingProjectId] = useState<string>('');
  const [linkingRuleSetId, setLinkingRuleSetId] = useState<string | null>(null);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  // ==========================================
  // STEP 3 TEMPLATE SYNTHESIS STATE (PRESERVED)
  // ==========================================
  const [publisher, setPublisher] = useState('Meridian Science / Journal of Sustainable Systems');
  const [columnLayout, setColumnLayout] = useState('Double column');
  const [referencingStyle, setReferencingStyle] = useState('Vancouver');
  const [documentClass, setDocumentClass] = useState('sn-jnl (LaTeX2e)');

  // Clean polling timer on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  // Update selectedProjectId when activeProject changes
  useEffect(() => {
    if (activeProject && !selectedProjectId) {
      setSelectedProjectId(activeProject.id);
    }
  }, [activeProject]);

  // Load Recent Extractions & Rule Sets
  const loadRecentExtractions = async () => {
    setIsLoadingRecents(true);
    try {
      const res = await getGuidelineExtractions(1, 10);
      setRecentExtractions(Array.isArray(res) ? res : (res?.items || []));
    } catch (err) {
      console.error('Failed to load recent extractions:', err);
    } finally {
      setIsLoadingRecents(false);
    }
  };

  const loadRuleSets = async () => {
    setIsLoadingRuleSets(true);
    try {
      const res = await getGuidelineRuleSets({ pageSize: 50 });
      setRuleSets(Array.isArray(res) ? res : (res?.items || []));
    } catch (err) {
      console.error('Failed to load rule sets:', err);
    } finally {
      setIsLoadingRuleSets(false);
    }
  };

  useEffect(() => {
    loadRecentExtractions();
    loadRuleSets();
  }, []);

  // ==========================================
  // EXTRACTION INITIATION & POLLING
  // ==========================================
  const startPolling = (jobId: string) => {
    if (pollingRef.current) clearInterval(pollingRef.current);

    pollingRef.current = setInterval(async () => {
      try {
        const job = await getGuidelineExtraction(jobId);
        setCurrentJob(job);

        if (job.status === 'completed') {
          if (pollingRef.current) clearInterval(pollingRef.current);
          // Set up review state
          if (job.draft?.rules) {
            setReviewRules(JSON.parse(JSON.stringify(job.draft.rules)));
          }
          if (job.draft?.fields) {
            setReviewFields(JSON.parse(JSON.stringify(job.draft.fields)));
          }
          const journalObj = journals.find(j => j.id === job.journalId);
          const defaultName = journalObj ? `${journalObj.title} Guidelines` : (job.sourceUrl ? safeHostname(job.sourceUrl) : 'Extracted Guidelines');
          setRuleSetName(defaultName);
          setExtractionSubStep('review');
          loadRecentExtractions();
          addActivity('Guideline extraction completed', defaultName, 'journal');
        } else if (job.status === 'failed') {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setJobError(job.error?.message || 'Guideline extraction failed. Please verify the URL or text and try again.');
          setExtractionSubStep('input');
          loadRecentExtractions();
        }
      } catch (err: any) {
        console.error('Polling error:', err);
      }
    }, 1500);
  };

  const handleStartExtraction = async () => {
    setJobError(null);
    if (inputMode === 'url' && !guidelinesUrl.trim()) {
      setJobError('Please provide a valid publisher guidelines URL.');
      return;
    }
    if (inputMode === 'text' && !guidelinesText.trim()) {
      setJobError('Please paste guidelines text to extract.');
      return;
    }

    setIsStartingJob(true);
    try {
      const payload: any = {
        sourceType: inputMode,
        journalId: selectedJournalId || undefined,
        projectId: selectedProjectId || undefined,
      };

      if (inputMode === 'url') {
        payload.url = guidelinesUrl.trim();
      } else {
        payload.text = guidelinesText.trim();
      }

      const job = await createGuidelineExtraction(payload);
      setCurrentJob(job);
      setExtractionSubStep('processing');
      startPolling(job.id);
      loadRecentExtractions();
    } catch (err: any) {
      setJobError(err.message || 'Failed to initiate extraction job.');
    } finally {
      setIsStartingJob(false);
    }
  };

  const handleCancelJob = async () => {
    if (!currentJob) return;
    try {
      await cancelGuidelineExtraction(currentJob.id);
      if (pollingRef.current) clearInterval(pollingRef.current);
      setExtractionSubStep('input');
      loadRecentExtractions();
    } catch (err: any) {
      alert(`Could not cancel job: ${err.message}`);
    }
  };

  const handleRetryJob = async (jobId: string) => {
    try {
      const job = await retryGuidelineExtraction(jobId);
      setCurrentJob(job);
      setExtractionSubStep('processing');
      startPolling(job.id);
      loadRecentExtractions();
    } catch (err: any) {
      alert(`Could not retry extraction: ${err.message}`);
    }
  };

  const resumeExtractionReview = (extraction: GuidelineExtractionJob) => {
    setCurrentJob(extraction);
    if (extraction.draft?.rules) {
      setReviewRules(JSON.parse(JSON.stringify(extraction.draft.rules)));
    }
    if (extraction.draft?.fields) {
      setReviewFields(JSON.parse(JSON.stringify(extraction.draft.fields)));
    }
    const journalObj = journals.find(j => j.id === extraction.journalId);
    const defaultName = journalObj ? `${journalObj.title} Rules` : 'Extracted Rules';
    setRuleSetName(defaultName);
    setExtractionSubStep('review');
    setActiveTab('extract');
  };

  // ==========================================
  // REVIEW & EDIT HELPERS
  // ==========================================
  const updateRuleField = (category: string, field: string, val: any) => {
    const updated = { ...reviewRules };
    if (!updated[category]) updated[category] = {};
    updated[category][field] = val;
    setReviewRules(updated);

    const path = `${category}.${field}`;
    setReviewFields({
      ...reviewFields,
      [path]: {
        confidence: 'high',
        evidence: 'User modified during manual review.',
        edited: true
      }
    });
  };

  // Find low confidence fields
  const lowConfidenceItems = Object.entries(reviewFields).filter(
    ([_, prov]) => prov.confidence === 'low' && !prov.edited
  );

  const handleConfirmAndSaveRules = async () => {
    if (!currentJob || !reviewRules) return;
    if (lowConfidenceItems.length > 0 && !reviewedAllFlags) {
      alert('Please check the confirmation box acknowledging you have reviewed flagged low-confidence fields.');
      return;
    }
    if (!ruleSetName.trim()) {
      alert('Please specify a name for this Rule Set.');
      return;
    }

    setIsConfirming(true);
    try {
      const createdRuleSet = await confirmGuidelineExtraction(currentJob.id, {
        name: ruleSetName.trim(),
        rules: reviewRules,
        journalId: selectedJournalId || undefined,
        projectId: selectedProjectId || undefined,
        acknowledgedFields: lowConfidenceItems.map(([path]) => path),
      });

      setReviewSuccessMsg(`Rule Set "${createdRuleSet.name}" saved successfully!`);
      addActivity('Guideline rule set created', createdRuleSet.name, 'journal');
      loadRuleSets();

      setTimeout(() => {
        setReviewSuccessMsg(null);
        setExtractionSubStep('input');
        setActiveTab('rulesets');
      }, 1500);
    } catch (err: any) {
      alert(`Failed to confirm rule set: ${err.message}`);
    } finally {
      setIsConfirming(false);
    }
  };

  // ==========================================
  // RULE SETS LIBRARY ACTIONS
  // ==========================================
  const handleSelectRuleSetForDetails = async (ruleSet: GuidelineRuleSet) => {
    setSelectedRuleSetForView(ruleSet);
    try {
      const versions = await getGuidelineRuleSetVersions(ruleSet.id);
      setVersionHistory(versions.sort((a, b) => b.version - a.version));
    } catch (err) {
      console.error(err);
      setVersionHistory([ruleSet]);
    }
  };

  const handleDuplicateRuleSet = async (ruleSet: GuidelineRuleSet) => {
    try {
      const copy = await copyGuidelineRuleSet(ruleSet.id);
      setActionSuccessMsg(`Created copy: ${copy.name}`);
      loadRuleSets();
      setTimeout(() => setActionSuccessMsg(null), 3000);
    } catch (err: any) {
      alert(`Failed to duplicate: ${err.message}`);
    }
  };

  const handleDeleteRuleSet = async (ruleSet: GuidelineRuleSet) => {
    if (ruleSet.isSystem || ruleSet.origin === 'seed') {
      alert('Built-in seed rule sets cannot be deleted.');
      return;
    }
    if (!confirm(`Are you sure you want to delete "${ruleSet.name}"? This cannot be undone.`)) return;

    try {
      await deleteGuidelineRuleSet(ruleSet.id);
      if (selectedRuleSetForView?.id === ruleSet.id) {
        setSelectedRuleSetForView(null);
      }
      loadRuleSets();
    } catch (err: any) {
      alert(`Failed to delete: ${err.message}`);
    }
  };

  const handleActivateVersion = async (versionRuleSet: GuidelineRuleSet) => {
    try {
      const activated = await activateGuidelineRuleSet(versionRuleSet.id);
      setSelectedRuleSetForView(activated);
      setActionSuccessMsg(`Version ${activated.version} is now active!`);
      loadRuleSets();
      setTimeout(() => setActionSuccessMsg(null), 3000);
    } catch (err: any) {
      alert(`Failed to activate version: ${err.message}`);
    }
  };

  const handleLinkToProject = async (ruleSetId: string, projectId: string) => {
    if (!projectId) return;
    try {
      await linkProjectGuidelineRule(projectId, ruleSetId);
      setActionSuccessMsg('Rule set successfully linked to project!');
      setLinkingRuleSetId(null);
      loadRuleSets();
      setTimeout(() => setActionSuccessMsg(null), 3000);
    } catch (err: any) {
      alert(`Failed to link rule set: ${err.message}`);
    }
  };

  // ==========================================
  // STEP 3 TEMPLATE SYNTHESIS ACTIONS
  // ==========================================
  const handleDownloadTemplate = () => {
    addActivity('LaTeX template generated', `${referencingStyle} · ${columnLayout}`, 'conversion');
    const texContent = `% PublishAid Auto-Generated LaTeX Template
% Venue: ${publisher}
% Citation Style: ${referencingStyle}
% Layout: ${columnLayout}

\\documentclass[${columnLayout === 'Double column' ? 'twocolumn' : 'onecolumn'},10pt]{article}
\\usepackage[utf8]{inputenc}
\\usepackage{amsmath,amsfonts,amssymb}
\\usepackage{graphicx}
\\usepackage{cite}
\\usepackage[margin=20mm]{geometry}

\\title{Manuscript Title Here}
\\author{Author One$^{1}$, Author Two$^{2}$}
\\date{\\today}

\\begin{document}
\\maketitle

\\begin{abstract}
Your structured abstract (under 250 words).
\\end{abstract}

\\section{Introduction}
Introduction section conforming to ${publisher} specifications.

\\section{Methods}
Methodological details and study framework.

\\section{Results}
Empirical findings and statistical metrics.

\\section{Discussion}
Contextual discussion and limitations.

\\section*{Declarations}
Funding, Conflict of Interest, and Data Availability.

\\bibliographystyle{unsrt}
\\bibliography{references}

\\end{document}
`;
    const blob = new Blob([texContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'publishaid_template_package.tex';
    a.click();
    URL.revokeObjectURL(url);
  };

  // Helper for confidence badge
  const renderConfidenceBadge = (path: string) => {
    const prov = reviewFields[path];
    if (prov?.edited) {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-teal-700 bg-teal-50 border border-teal-200 px-1.5 py-0.5 rounded">
          <Check className="w-3 h-3" /> Edited
        </span>
      );
    }
    if (!prov) return null;

    if (prov.confidence === 'high') {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded" title={prov.evidence || ''}>
          <ShieldCheck className="w-3 h-3" /> High
        </span>
      );
    } else if (prov.confidence === 'medium') {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded" title={prov.evidence || ''}>
          <AlertTriangle className="w-3 h-3" /> Medium
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-1.5 py-0.5 rounded" title={prov.evidence || ''}>
          <AlertTriangle className="w-3 h-3" /> Low
        </span>
      );
    }
  };

  // Filtered rule sets list
  const filteredRuleSets = (Array.isArray(ruleSets) ? ruleSets : []).filter(rs => {
    if (!rs) return false;
    const isSeed = rs.isSystem || rs.origin === 'seed';
    if (ruleSetFilter === 'seed') return isSeed;
    if (ruleSetFilter === 'custom') return !isSeed;
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Banner / Heading */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Building2 className="w-7 h-7 text-[#0F766E]" />
            Guidelines & Template Studio
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Extract publisher author instructions, customize machine-readable rule sets, and generate compliant LaTeX templates.
          </p>
        </div>

        {/* Primary Page Navigation Tabs */}
        <div className="flex items-center bg-slate-100 p-1 rounded-xl self-start sm:self-auto border border-slate-200">
          <button
            onClick={() => setActiveTab('extract')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'extract'
                ? 'bg-white text-slate-900 shadow-2xs font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-[#0F766E]" />
            Extract & Review
          </button>
          <button
            onClick={() => setActiveTab('rulesets')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'rulesets'
                ? 'bg-white text-slate-900 shadow-2xs font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-blue-600" />
            Rule Sets Library ({ruleSets.length})
          </button>
          <button
            onClick={() => setActiveTab('template')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'template'
                ? 'bg-white text-slate-900 shadow-2xs font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Download className="w-3.5 h-3.5 text-purple-600" />
            LaTeX Template Generator
          </button>
        </div>
      </div>

      {actionSuccessMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          {actionSuccessMsg}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: EXTRACT & REVIEW                                                   */}
      {/* ========================================================================= */}
      {activeTab === 'extract' && (
        <div className="space-y-6">
          {/* Progress / Step indicator inside Tab 1 */}
          <div className="flex items-center justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
            <div className="flex items-center gap-3">
              <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                extractionSubStep === 'input' ? 'bg-[#0F766E] text-white' : 'bg-slate-100 text-slate-500'
              }`}>
                1
              </span>
              <span className={`text-xs font-semibold ${extractionSubStep === 'input' ? 'text-slate-900 font-bold' : 'text-slate-500'}`}>
                Source Guidelines
              </span>
            </div>
            <div className="w-12 h-px bg-slate-200" />
            <div className="flex items-center gap-3">
              <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                extractionSubStep === 'processing' ? 'bg-[#0F766E] text-white' : 'bg-slate-100 text-slate-500'
              }`}>
                2
              </span>
              <span className={`text-xs font-semibold ${extractionSubStep === 'processing' ? 'text-slate-900 font-bold' : 'text-slate-500'}`}>
                Extraction Engine
              </span>
            </div>
            <div className="w-12 h-px bg-slate-200" />
            <div className="flex items-center gap-3">
              <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                extractionSubStep === 'review' ? 'bg-[#0F766E] text-white' : 'bg-slate-100 text-slate-500'
              }`}>
                3
              </span>
              <span className={`text-xs font-semibold ${extractionSubStep === 'review' ? 'text-slate-900 font-bold' : 'text-slate-500'}`}>
                Verify & Save Rules
              </span>
            </div>
          </div>

          {/* SUB-STEP 1: INPUT FORM */}
          {extractionSubStep === 'input' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Form card */}
              <div className="lg:col-span-2 bg-white rounded-2xl p-6 border border-slate-200 shadow-2xs space-y-5">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Extract Publisher Guidelines</h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Provide the official Instructions for Authors page URL or paste the raw text. PublishAid extracts layout, font, citation, and submission specifications.
                  </p>
                </div>

                {jobError && (
                  <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2.5">
                    <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <span>{jobError}</span>
                  </div>
                )}

                {/* Input Mode Toggle */}
                <div className="flex items-center gap-3">
                  <span className="text-xs font-bold text-slate-700">Source Mode:</span>
                  <div className="flex items-center bg-slate-100 p-1 rounded-lg border border-slate-200">
                    <button
                      onClick={() => setInputMode('url')}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-all ${
                        inputMode === 'url' ? 'bg-white text-slate-900 shadow-2xs font-bold' : 'text-slate-600'
                      }`}
                    >
                      <Globe className="w-3.5 h-3.5 text-[#0F766E]" />
                      Publisher URL
                    </button>
                    <button
                      onClick={() => setInputMode('text')}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-all ${
                        inputMode === 'text' ? 'bg-white text-slate-900 shadow-2xs font-bold' : 'text-slate-600'
                      }`}
                    >
                      <Clipboard className="w-3.5 h-3.5 text-blue-600" />
                      Paste Guidelines Text
                    </button>
                  </div>
                </div>

                {/* Mode: URL */}
                {inputMode === 'url' && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Guidelines Webpage URL <span className="text-rose-500">*</span>
                    </label>
                    <div className="relative">
                      <Globe className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                      <input
                        type="url"
                        placeholder="https://www.nature.com/nature/for-authors/formatting-guide"
                        value={guidelinesUrl}
                        onChange={(e) => setGuidelinesUrl(e.target.value)}
                        className="w-full pl-10 pr-3.5 h-[42px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none"
                      />
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1">
                      Safe extraction with SSRF security guard, anti-crawl filtering, and multi-chunk analysis.
                    </p>
                  </div>
                )}

                {/* Mode: Text */}
                {inputMode === 'text' && (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="block text-xs font-semibold text-slate-700">
                        Guidelines Text <span className="text-rose-500">*</span>
                      </label>
                      <span className="text-[11px] text-slate-400">
                        {guidelinesText.length} / 100,000 characters
                      </span>
                    </div>
                    <textarea
                      rows={7}
                      placeholder="Paste author instructions, formatting limits, reference instructions, and submission requirements here..."
                      value={guidelinesText}
                      maxLength={100000}
                      onChange={(e) => setGuidelinesText(e.target.value)}
                      className="w-full p-3 rounded-xl border border-slate-200 text-xs font-mono bg-white focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none resize-none leading-relaxed"
                    />
                  </div>
                )}

                {/* Target Metadata Selectors */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Associated Journal (Optional)
                    </label>
                    <select
                      value={selectedJournalId}
                      onChange={(e) => setSelectedJournalId(e.target.value)}
                      className="w-full px-3 h-[40px] rounded-xl border border-slate-200 text-xs bg-white focus:border-[#0F766E] outline-none"
                    >
                      <option value="">-- None (Standalone Rule Set) --</option>
                      {journals.map((j) => (
                        <option key={j.id} value={j.id}>
                          {j.title} ({j.publisher})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Link Directly to Project (Optional)
                    </label>
                    <select
                      value={selectedProjectId}
                      onChange={(e) => setSelectedProjectId(e.target.value)}
                      className="w-full px-3 h-[40px] rounded-xl border border-slate-200 text-xs bg-white focus:border-[#0F766E] outline-none"
                    >
                      <option value="">-- Do Not Link Immediately --</option>
                      {projects.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.title}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Submit Action */}
                <div className="pt-3 flex items-center justify-between">
                  <div className="text-[11px] text-slate-400">
                    Daily Quota: 20 extractions · Concurrent: 2
                  </div>
                  <Button
                    onClick={handleStartExtraction}
                    disabled={isStartingJob}
                    leftIcon={isStartingJob ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  >
                    {isStartingJob ? 'Initiating Extraction...' : 'Fetch & Parse Guidelines'}
                  </Button>
                </div>
              </div>

              {/* Side Info & Recents */}
              <div className="space-y-4">
                {/* Seed Rule Set Shortcut Banner */}
                <div className="bg-gradient-to-br from-teal-50 to-emerald-50 border border-teal-200/80 rounded-2xl p-5">
                  <div className="flex items-center gap-2 text-teal-800 font-bold text-xs uppercase tracking-wider">
                    <ShieldCheck className="w-4 h-4 text-[#0F766E]" />
                    Built-in Rule Sets Available
                  </div>
                  <p className="text-xs text-teal-900 mt-2 leading-relaxed">
                    Looking for IEEE TPAMI, Nature, Elsevier Neurocomputing, Springer LNCS, or ACM TOG? Hand-verified seed rules are pre-loaded in your library.
                  </p>
                  <button
                    onClick={() => {
                      setActiveTab('rulesets');
                      setRuleSetFilter('seed');
                    }}
                    className="mt-3 text-xs font-bold text-[#0F766E] hover:underline flex items-center gap-1"
                  >
                    Browse Seed Rule Sets <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Recent Extractions */}
                <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-2xs space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      Recent Extractions
                    </h3>
                    <button
                      onClick={loadRecentExtractions}
                      disabled={isLoadingRecents}
                      className="text-slate-400 hover:text-slate-600"
                    >
                      <RefreshCw className={`w-3 h-3 ${isLoadingRecents ? 'animate-spin' : ''}`} />
                    </button>
                  </div>

                  {recentExtractions.length === 0 ? (
                    <p className="text-xs text-slate-400 py-2">No previous extractions yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {recentExtractions.slice(0, 5).map((ext) => (
                        <div
                          key={ext.id}
                          className="p-2.5 rounded-xl border border-slate-100 hover:border-slate-200 bg-slate-50/50 flex items-center justify-between text-xs"
                        >
                          <div className="min-w-0 pr-2">
                            <div className="font-semibold text-slate-800 truncate">
                              {safeHostname(ext.sourceUrl)}
                            </div>
                            <div className="text-[10px] text-slate-400 flex items-center gap-1.5 mt-0.5">
                              <span>{safeFormatDate(ext.createdAt)}</span>
                              <span>•</span>
                              <span className={`font-semibold capitalize ${
                                ext.status === 'completed'
                                  ? 'text-emerald-600'
                                  : ext.status === 'failed'
                                  ? 'text-rose-600'
                                  : 'text-amber-600'
                              }`}>
                                {ext.status}
                              </span>
                              {ext.status === 'failed' && ext.error?.message && (
                                <span className="text-[10px] text-rose-500 truncate max-w-[120px]" title={ext.error.message}>
                                  ({ext.error.message})
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {ext.status === 'completed' && (
                              <button
                                onClick={() => resumeExtractionReview(ext)}
                                className="text-[11px] font-bold text-[#0F766E] bg-teal-50 hover:bg-teal-100 border border-teal-200 px-2.5 py-1 rounded-lg"
                              >
                                Review
                              </button>
                            )}
                            {ext.status === 'failed' && (
                              <button
                                onClick={() => handleRetryJob(ext.id)}
                                className="text-[11px] font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200 px-2.5 py-1 rounded-lg"
                              >
                                Retry
                              </button>
                            )}
                            {ext.status === 'running' && (
                              <span className="text-[10px] text-amber-600 flex items-center gap-1">
                                <Loader2 className="w-3 h-3 animate-spin" /> In progress
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* SUB-STEP 2: PROCESSING / PROGRESS */}
          {extractionSubStep === 'processing' && currentJob && (
            <div className="bg-white rounded-2xl p-8 border border-slate-200 shadow-2xs max-w-2xl mx-auto text-center space-y-6">
              <div className="w-16 h-16 rounded-full bg-teal-50 border border-teal-200 flex items-center justify-center mx-auto text-[#0F766E]">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>

              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  {currentJob.step === 'fetching' && 'Fetching guidelines webpage...'}
                  {currentJob.step === 'cleaning' && 'Sanitizing and chunking text...'}
                  {currentJob.step === 'extracting' && 'Extracting formatting rules with AI...'}
                  {currentJob.step === 'validating' && 'Grounding evidence and checking schema...'}
                  {currentJob.step === 'queued' && 'Queued for processing...'}
                  {!currentJob.step && 'Analyzing Guidelines...'}
                </h2>
                <p className="text-xs text-slate-500 mt-1">
                  PublishAid is analyzing the instructions to extract layout, font, reference, and submission rules.
                </p>
              </div>

              {/* Stage Stepper */}
              <div className="flex items-center justify-between text-xs text-slate-500 px-4">
                <span className={currentJob.step === 'fetching' ? 'text-[#0F766E] font-bold' : ''}>1. Fetch</span>
                <span>•</span>
                <span className={currentJob.step === 'cleaning' ? 'text-[#0F766E] font-bold' : ''}>2. Clean</span>
                <span>•</span>
                <span className={currentJob.step === 'extracting' ? 'text-[#0F766E] font-bold' : ''}>3. Extract</span>
                <span>•</span>
                <span className={currentJob.step === 'validating' ? 'text-[#0F766E] font-bold' : ''}>4. Validate</span>
              </div>

              <div className="pt-4 border-t border-slate-100">
                <Button variant="secondary" onClick={handleCancelJob} leftIcon={<XCircle className="w-4 h-4" />}>
                  Cancel Extraction
                </Button>
              </div>
            </div>
          )}

          {/* SUB-STEP 3: REVIEW & EDIT EXTRACTED RULES */}
          {extractionSubStep === 'review' && reviewRules && (
            <div className="space-y-6">
              {/* Review Header Banner */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-2xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900">Review & Confirm Extracted Rules</h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Verify extracted constraints against publisher grounding quotes. Correct any flagged fields before saving.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => setExtractionSubStep('input')}
                      leftIcon={<ArrowLeft className="w-4 h-4" />}
                    >
                      Back
                    </Button>
                    <Button
                      onClick={handleConfirmAndSaveRules}
                      disabled={isConfirming}
                      leftIcon={isConfirming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    >
                      {isConfirming ? 'Saving Rules...' : 'Save as Rule Set'}
                    </Button>
                  </div>
                </div>

                {reviewSuccessMsg && (
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    {reviewSuccessMsg}
                  </div>
                )}

                {/* Low Confidence Warning Guard */}
                {lowConfidenceItems.length > 0 && (
                  <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 space-y-2">
                    <div className="flex items-center gap-2 font-bold text-amber-800">
                      <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                      Attention: {lowConfidenceItems.length} field(s) have low confidence
                    </div>
                    <p className="text-amber-700 leading-relaxed">
                      Please inspect the flagged fields below. Click their quote badges to view the source text snippet and edit if needed.
                    </p>
                    <label className="flex items-center gap-2 font-semibold text-slate-800 pt-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={reviewedAllFlags}
                        onChange={(e) => setReviewedAllFlags(e.target.checked)}
                        className="rounded border-amber-300 text-[#0F766E] focus:ring-[#0F766E]"
                      />
                      I have verified all flagged fields against publisher guidelines
                    </label>
                  </div>
                )}

                {/* Rule Set Metadata Name */}
                <div className="pt-2 border-t border-slate-100">
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Rule Set Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={ruleSetName}
                    onChange={(e) => setRuleSetName(e.target.value)}
                    placeholder="e.g. Nature Author Guidelines (2026)"
                    className="w-full px-3.5 h-[38px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none"
                  />
                </div>
              </div>

              {/* Category Sub-Tabs */}
              <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
                <button
                  onClick={() => setReviewCategory('documentStructure')}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    reviewCategory === 'documentStructure'
                      ? 'bg-[#0F766E] text-white shadow-2xs'
                      : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                  }`}
                >
                  Document Structure
                </button>
                <button
                  onClick={() => setReviewCategory('citations')}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    reviewCategory === 'citations'
                      ? 'bg-[#0F766E] text-white shadow-2xs'
                      : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                  }`}
                >
                  Citations & References
                </button>
                <button
                  onClick={() => setReviewCategory('figuresAndTables')}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    reviewCategory === 'figuresAndTables'
                      ? 'bg-[#0F766E] text-white shadow-2xs'
                      : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                  }`}
                >
                  Figures & Tables
                </button>
                <button
                  onClick={() => setReviewCategory('submissionStyle')}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    reviewCategory === 'submissionStyle'
                      ? 'bg-[#0F766E] text-white shadow-2xs'
                      : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                  }`}
                >
                  Submission & Style
                </button>
              </div>

              {/* Category Editors */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-2xs space-y-6">
                {/* 1. DOCUMENT STRUCTURE */}
                {reviewCategory === 'documentStructure' && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
                    {/* Word Count Max */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Word Count Max</label>
                        {renderConfidenceBadge('documentStructure.wordCountMax')}
                      </div>
                      <input
                        type="number"
                        value={reviewRules.documentStructure?.wordCountMax ?? ''}
                        onChange={(e) => updateRuleField('documentStructure', 'wordCountMax', e.target.value ? Number(e.target.value) : null)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                        placeholder="e.g. 8000"
                      />
                    </div>

                    {/* Abstract Limit */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Abstract Limit (words)</label>
                        {renderConfidenceBadge('documentStructure.abstractMaxWords')}
                      </div>
                      <input
                        type="number"
                        value={reviewRules.documentStructure?.abstractMaxWords ?? ''}
                        onChange={(e) => updateRuleField('documentStructure', 'abstractMaxWords', e.target.value ? Number(e.target.value) : null)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                        placeholder="e.g. 250"
                      />
                    </div>

                    {/* Column Layout */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Column Layout</label>
                        {renderConfidenceBadge('documentStructure.columns')}
                      </div>
                      <select
                        value={reviewRules.documentStructure?.columns ?? 1}
                        onChange={(e) => updateRuleField('documentStructure', 'columns', Number(e.target.value))}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value={1}>Single Column (1)</option>
                        <option value={2}>Double Column (2)</option>
                      </select>
                    </div>

                    {/* Line Spacing */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Line Spacing</label>
                        {renderConfidenceBadge('documentStructure.lineSpacing')}
                      </div>
                      <select
                        value={reviewRules.documentStructure?.lineSpacing ?? 'single'}
                        onChange={(e) => updateRuleField('documentStructure', 'lineSpacing', e.target.value)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value="single">Single (1.0)</option>
                        <option value="1.5">1.5 Lines</option>
                        <option value="double">Double (2.0)</option>
                      </select>
                    </div>

                    {/* Font Family */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Font Family</label>
                        {renderConfidenceBadge('documentStructure.fontFamily')}
                      </div>
                      <input
                        type="text"
                        value={reviewRules.documentStructure?.fontFamily ?? ''}
                        onChange={(e) => updateRuleField('documentStructure', 'fontFamily', e.target.value)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                        placeholder="e.g. Times New Roman"
                      />
                    </div>

                    {/* Font Size (Body) */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Body Font Size (pt)</label>
                        {renderConfidenceBadge('documentStructure.fontSizePt')}
                      </div>
                      <input
                        type="number"
                        step="0.5"
                        value={reviewRules.documentStructure?.fontSizePt ?? 10}
                        onChange={(e) => updateRuleField('documentStructure', 'fontSizePt', Number(e.target.value))}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                        placeholder="e.g. 10"
                      />
                    </div>
                  </div>
                )}

                {/* 2. CITATIONS & REFERENCES */}
                {reviewCategory === 'citations' && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
                    {/* Style */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Citation Style</label>
                        {renderConfidenceBadge('citations.style')}
                      </div>
                      <select
                        value={reviewRules.citations?.style ?? 'vancouver'}
                        onChange={(e) => updateRuleField('citations', 'style', e.target.value)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value="vancouver">Vancouver (Numbered [1])</option>
                        <option value="ieee">IEEE</option>
                        <option value="apa">APA 7th</option>
                        <option value="harvard">Harvard (Author-Date)</option>
                        <option value="nature">Nature Format</option>
                        <option value="chicago">Chicago</option>
                      </select>
                    </div>

                    {/* Citation Format */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Citation Format</label>
                        {renderConfidenceBadge('citations.format')}
                      </div>
                      <select
                        value={reviewRules.citations?.format ?? 'numeric_bracket'}
                        onChange={(e) => updateRuleField('citations', 'format', e.target.value)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value="numeric_bracket">Numbered bracket [1]</option>
                        <option value="superscript">Superscript¹</option>
                        <option value="author_year">Author-Date (Smith 2020)</option>
                      </select>
                    </div>

                    {/* Bibliography Sort */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Bibliography Order</label>
                        {renderConfidenceBadge('citations.bibliographySort')}
                      </div>
                      <select
                        value={reviewRules.citations?.bibliographySort ?? 'appearance'}
                        onChange={(e) => updateRuleField('citations', 'bibliographySort', e.target.value)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value="appearance">Order of Appearance</option>
                        <option value="alphabetical">Alphabetical by Author</option>
                      </select>
                    </div>
                  </div>
                )}

                {/* 3. FIGURES & TABLES */}
                {reviewCategory === 'figuresAndTables' && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
                    {/* Min DPI */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Minimum DPI / Resolution</label>
                        {renderConfidenceBadge('figuresAndTables.minDpi')}
                      </div>
                      <input
                        type="number"
                        value={reviewRules.figuresAndTables?.minDpi ?? 300}
                        onChange={(e) => updateRuleField('figuresAndTables', 'minDpi', Number(e.target.value))}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                        placeholder="e.g. 300"
                      />
                    </div>

                    {/* Placement */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Figure Placement</label>
                        {renderConfidenceBadge('figuresAndTables.placement')}
                      </div>
                      <select
                        value={reviewRules.figuresAndTables?.placement ?? 'inline'}
                        onChange={(e) => updateRuleField('figuresAndTables', 'placement', e.target.value)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value="inline">Inline with text</option>
                        <option value="end_of_manuscript">End of Manuscript</option>
                        <option value="separate_files">Separate Uploads</option>
                      </select>
                    </div>

                    {/* Caption Position */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Figure Caption Position</label>
                        {renderConfidenceBadge('figuresAndTables.captionPosition')}
                      </div>
                      <select
                        value={reviewRules.figuresAndTables?.captionPosition ?? 'below'}
                        onChange={(e) => updateRuleField('figuresAndTables', 'captionPosition', e.target.value)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value="below">Below figure</option>
                        <option value="above">Above figure</option>
                      </select>
                    </div>
                  </div>
                )}

                {/* 4. SUBMISSION & STYLE */}
                {reviewCategory === 'submissionStyle' && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
                    {/* Review Type */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Peer Review Anonymity</label>
                        {renderConfidenceBadge('submissionStyle.reviewType')}
                      </div>
                      <select
                        value={reviewRules.submissionStyle?.reviewType ?? 'single_blind'}
                        onChange={(e) => updateRuleField('submissionStyle', 'reviewType', e.target.value)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value="single_blind">Single Blind (Authors known to reviewers)</option>
                        <option value="double_blind">Double Blind (Fully anonymized)</option>
                        <option value="open">Open Peer Review</option>
                      </select>
                    </div>

                    {/* Cover Letter Required */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Cover Letter Mandatory</label>
                        {renderConfidenceBadge('submissionStyle.coverLetterRequired')}
                      </div>
                      <select
                        value={reviewRules.submissionStyle?.coverLetterRequired ? 'yes' : 'no'}
                        onChange={(e) => updateRuleField('submissionStyle', 'coverLetterRequired', e.target.value === 'yes')}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value="yes">Yes, Mandatory</option>
                        <option value="no">No, Optional</option>
                      </select>
                    </div>

                    {/* Keywords Separator */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700">Keyword Separator</label>
                        {renderConfidenceBadge('submissionStyle.keywordSeparator')}
                      </div>
                      <select
                        value={reviewRules.submissionStyle?.keywordSeparator ?? ';'}
                        onChange={(e) => updateRuleField('submissionStyle', 'keywordSeparator', e.target.value)}
                        className="w-full px-3 h-[36px] rounded-lg border border-slate-200 text-xs bg-white"
                      >
                        <option value=";">Semicolon (;)</option>
                        <option value=",">Comma (,)</option>
                        <option value="bullet">Bullet (•)</option>
                      </select>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: RULE SETS LIBRARY                                                 */}
      {/* ========================================================================= */}
      {activeTab === 'rulesets' && (
        <div className="space-y-6">
          {/* Header & Filter Controls */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Guideline Rule Sets Library</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Machine-readable formatting rules. Built-in seed sets and your custom extractions.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center bg-slate-100 p-1 rounded-lg border border-slate-200">
                <button
                  onClick={() => setRuleSetFilter('all')}
                  className={`px-3 py-1 rounded-md text-xs font-semibold ${
                    ruleSetFilter === 'all' ? 'bg-white text-slate-900 shadow-2xs font-bold' : 'text-slate-600'
                  }`}
                >
                  All ({ruleSets.length})
                </button>
                <button
                  onClick={() => setRuleSetFilter('custom')}
                  className={`px-3 py-1 rounded-md text-xs font-semibold ${
                    ruleSetFilter === 'custom' ? 'bg-white text-slate-900 shadow-2xs font-bold' : 'text-slate-600'
                  }`}
                >
                  Custom
                </button>
                <button
                  onClick={() => setRuleSetFilter('seed')}
                  className={`px-3 py-1 rounded-md text-xs font-semibold ${
                    ruleSetFilter === 'seed' ? 'bg-white text-slate-900 shadow-2xs font-bold' : 'text-slate-600'
                  }`}
                >
                  Built-in Seeds
                </button>
              </div>

              <Button
                variant="secondary"
                size="sm"
                onClick={loadRuleSets}
                disabled={isLoadingRuleSets}
                leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoadingRuleSets ? 'animate-spin' : ''}`} />}
              >
                Refresh
              </Button>
            </div>
          </div>

          {/* Grid of Rule Sets */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredRuleSets.map((rs) => {
              const doc = rs.rules?.documentStructure;
              const cite = rs.rules?.citations;
              const sub = rs.rules?.submissionStyle;
              const isSeed = rs.isSystem || rs.origin === 'seed';

              return (
                <div
                  key={rs.id}
                  className="bg-white rounded-2xl p-5 border border-slate-200 shadow-2xs hover:shadow-sm transition-all flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="font-bold text-sm text-slate-900 leading-snug">{rs.name}</h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                            v{rs.version}
                          </span>
                          {isSeed ? (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-teal-50 text-teal-700 border border-teal-200">
                              Built-in Seed
                            </span>
                          ) : (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                              Custom Rule Set
                            </span>
                          )}
                          {rs.isActive && (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                              Active
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-1">
                        <button
                          title="Duplicate Rule Set"
                          onClick={() => handleDuplicateRuleSet(rs)}
                          className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        {!isSeed && (
                          <button
                            title="Delete Rule Set"
                            onClick={() => handleDeleteRuleSet(rs)}
                            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Summary Highlights */}
                    <div className="grid grid-cols-2 gap-2 text-[11px] bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                      <div>
                        <span className="text-slate-400 block text-[10px]">Max Words</span>
                        <span className="font-semibold text-slate-700">
                          {doc?.wordCountMax ? `${doc.wordCountMax.toLocaleString()} words` : 'Unspecified'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Layout</span>
                        <span className="font-semibold text-slate-700">
                          {doc?.columns === 2 ? 'Double Column' : 'Single Column'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Citation Style</span>
                        <span className="font-semibold text-slate-700 capitalize">
                          {cite?.style || 'Vancouver'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Review Type</span>
                        <span className="font-semibold text-slate-700 capitalize">
                          {(sub?.reviewType || 'Single Blind').replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions Bar */}
                  <div className="pt-4 mt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                    <button
                      onClick={() => handleSelectRuleSetForDetails(rs)}
                      className="text-xs font-bold text-slate-600 hover:text-slate-900"
                    >
                      Inspect Rules
                    </button>

                    <Button
                      size="sm"
                      variant="secondary"
                      leftIcon={<Link2 className="w-3 h-3 text-[#0F766E]" />}
                      onClick={() => {
                        setLinkingRuleSetId(rs.id);
                        if (activeProject) setLinkingProjectId(activeProject.id);
                      }}
                    >
                      Use for Project
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Modal / Dialog for Linking to Project */}
          {linkingRuleSetId && (
            <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fade-in">
              <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h3 className="font-bold text-slate-900 text-sm">Link Rule Set to Project</h3>
                  <button onClick={() => setLinkingRuleSetId(null)} className="text-slate-400 hover:text-slate-600">
                    <XCircle className="w-5 h-5" />
                  </button>
                </div>
                <p className="text-xs text-slate-500">
                  Select which workspace manuscript project should enforce these guideline rules for validation and template generation:
                </p>

                <select
                  value={linkingProjectId}
                  onChange={(e) => setLinkingProjectId(e.target.value)}
                  className="w-full px-3 h-[40px] rounded-xl border border-slate-200 text-xs bg-white focus:border-[#0F766E] outline-none"
                >
                  <option value="">-- Choose Project --</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title}
                    </option>
                  ))}
                </select>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <Button variant="secondary" size="sm" onClick={() => setLinkingRuleSetId(null)}>
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    disabled={!linkingProjectId}
                    onClick={() => handleLinkToProject(linkingRuleSetId, linkingProjectId)}
                  >
                    Confirm & Link
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Inspect Details Drawer / Modal */}
          {selectedRuleSetForView && (
            <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fade-in">
              <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-xl border border-slate-200 space-y-5 max-h-[85vh] overflow-y-auto">
                <div className="flex items-start justify-between border-b border-slate-100 pb-3">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">{selectedRuleSetForView.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                        v{selectedRuleSetForView.version}
                      </span>
                      {(selectedRuleSetForView.isSystem || selectedRuleSetForView.origin === 'seed') && (
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-teal-50 text-teal-700">
                          Built-in Seed
                        </span>
                      )}
                      <span className="text-xs text-slate-400">
                        Updated: {safeFormatDate(selectedRuleSetForView.updatedAt || selectedRuleSetForView.createdAt)}
                      </span>
                    </div>
                  </div>
                  <button onClick={() => setSelectedRuleSetForView(null)} className="text-slate-400 hover:text-slate-600">
                    <XCircle className="w-5 h-5" />
                  </button>
                </div>

                {/* Version History if multiple versions exist */}
                {versionHistory.length > 1 && (
                  <div className="bg-slate-50 p-3 rounded-xl border border-slate-200/80 space-y-2">
                    <span className="text-xs font-bold text-slate-700 block">Version History</span>
                    <div className="flex items-center gap-2 flex-wrap">
                      {versionHistory.map((vh) => (
                        <div key={vh.id} className="flex items-center gap-1.5">
                          <button
                            onClick={() => setSelectedRuleSetForView(vh)}
                            className={`text-xs px-2.5 py-1 rounded-lg border font-semibold ${
                              vh.id === selectedRuleSetForView.id
                                ? 'bg-[#0F766E] text-white border-[#0F766E]'
                                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
                            }`}
                          >
                            v{vh.version} {vh.isActive && '(Active)'}
                          </button>
                          {!vh.isActive && (
                            <button
                              onClick={() => handleActivateVersion(vh)}
                              className="text-[10px] text-teal-700 hover:underline font-bold"
                            >
                              Activate
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Formatted JSON / Spec View */}
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                    Rules Specification (v{selectedRuleSetForView.schemaVersion || 1})
                  </h4>
                  <pre className="p-4 bg-slate-900 text-teal-300 rounded-xl text-xs font-mono overflow-x-auto max-h-72">
                    {JSON.stringify(selectedRuleSetForView.rules, null, 2)}
                  </pre>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                  <Button variant="secondary" size="sm" onClick={() => setSelectedRuleSetForView(null)}>
                    Close
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: STEP 3 LATEX TEMPLATE GENERATOR (PRESERVED IN FULL)                */}
      {/* ========================================================================= */}
      {activeTab === 'template' && (
        <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-2xs space-y-6 animate-fade-in">
          <div>
            <h2 className="text-xl font-bold text-[#14283D]">Ready to generate template</h2>
            <p className="text-xs text-slate-500 mt-1">
              PublishAid compiles a custom LaTeX package tailored to the extracted guideline rules.
            </p>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-50/70 p-4 rounded-xl border border-slate-200/80 text-xs">
            <div>
              <span className="text-slate-400 block text-[11px]">Publisher & Venue</span>
              <span className="font-semibold text-slate-800 mt-0.5 block">{publisher}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[11px]">Layout & Style</span>
              <span className="font-semibold text-slate-800 mt-0.5 block">{columnLayout} · {referencingStyle}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[11px]">LaTeX Documentclass</span>
              <span className="font-semibold text-slate-800 mt-0.5 block">{documentClass}</span>
            </div>
          </div>

          {/* Quick Customization Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Column Layout</label>
              <select
                value={columnLayout}
                onChange={(e) => setColumnLayout(e.target.value)}
                className="w-full px-3 h-[38px] rounded-xl border border-slate-200 text-xs bg-white focus:border-[#0F766E] outline-none"
              >
                <option value="Double column">Double column</option>
                <option value="Single column">Single column</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Referencing Style</label>
              <select
                value={referencingStyle}
                onChange={(e) => setReferencingStyle(e.target.value)}
                className="w-full px-3 h-[38px] rounded-xl border border-slate-200 text-xs bg-white focus:border-[#0F766E] outline-none"
              >
                <option value="Vancouver">Vancouver (Numbered brackets [1])</option>
                <option value="APA 7">APA 7th Edition (Author, Year)</option>
                <option value="IEEE">IEEE Reference Style</option>
                <option value="Harvard">Harvard Referencing</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">LaTeX Class</label>
              <select
                value={documentClass}
                onChange={(e) => setDocumentClass(e.target.value)}
                className="w-full px-3 h-[38px] rounded-xl border border-slate-200 text-xs bg-white focus:border-[#0F766E] outline-none"
              >
                <option value="sn-jnl (LaTeX2e)">sn-jnl (LaTeX2e)</option>
                <option value="IEEEtran">IEEEtran</option>
                <option value="elsarticle">elsarticle</option>
                <option value="acmart">acmart</option>
              </select>
            </div>
          </div>

          {/* Synthesis Showcase */}
          <div className="p-5 bg-[#CCFBF1]/30 border border-[#99F6E4] rounded-2xl flex items-center justify-between">
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[#0F766E] text-white flex items-center justify-center">
                <FileCheck className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-[#14283D]">
                  publishaid_template_package.tex
                </h4>
                <p className="text-xs text-slate-500">
                  Standalone compilation archive with bibliography macros and preamble.
                </p>
              </div>
            </div>

            <Button
              onClick={handleDownloadTemplate}
              leftIcon={<Download className="w-4 h-4" />}
              className="shadow-sm"
            >
              Download Package
            </Button>
          </div>

          {/* Footer navigation */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <Button
              variant="secondary"
              onClick={() => setActiveTab('rulesets')}
              leftIcon={<ArrowLeft className="w-4 h-4" />}
            >
              Back to Rule Sets
            </Button>
            <Button
              onClick={() => alert('Template preferences linked to your active manuscript workspace.')}
              leftIcon={<CheckCircle2 className="w-4 h-4" />}
            >
              Confirm & Apply to Workspace
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
