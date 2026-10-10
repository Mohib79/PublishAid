import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Download,
  RotateCw,
  ArrowRight,
  Info,
  Loader2,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/StatusBadge';

export const ComplianceCheckerPage: React.FC = () => {
  const navigate = useNavigate();
  const { complianceReport, projects, journals, addActivity } = useApp();

  const [selectedProject, setSelectedProject] = useState('Urban green infrastructure and heat resilience');
  const [selectedJournal, setSelectedJournal] = useState('Journal of Sustainable Systems');
  const [isRunningCheck, setIsRunningCheck] = useState(false);

  const handleRunCheckAgain = () => {
    setIsRunningCheck(true);
    setTimeout(() => {
      setIsRunningCheck(false);
      addActivity('Compliance check completed', `${selectedProject} against ${selectedJournal}`, 'compliance');
    }, 1200);
  };

  const handleDownloadPdf = () => {
    const reportText = `PublishAid Pre-Submission Compliance Audit Report
Project: ${selectedProject}
Target Journal: ${selectedJournal}
Overall Result: FAILED (4 Passed, 2 Failed)
Audit Timestamp: ${new Date().toLocaleString()}

DETAILED AUDIT FINDINGS:
1. Manuscript word count: PASSED (6,420 words <= 8,000 max)
2. Abstract length: FAILED (286 words > 250 max limit)
3. Citation style: FAILED (APA 7 detected, Vancouver required)
4. Required sections: PASSED (Introduction, Methods, Results, Discussion present)
5. Figure resolution: PASSED (6 figures all >= 300 dpi)
6. Required declarations: PASSED (Funding, ethics, COI verified)

RECOMMENDED ACTIONABLE FIXES:
- Trim 36 words from the abstract text before final submission.
- Reformat in-text citations from author-year to numbered Vancouver brackets.
`;
    const blob = new Blob([reportText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'publishaid_compliance_audit_report.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Title & Download Action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
            Submit with confidence.
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Check your manuscript against the requirements of your target journal.
          </p>
        </div>

        <Button
          variant="secondary"
          onClick={handleDownloadPdf}
          leftIcon={<Download className="w-4 h-4 text-[#0F766E]" />}
          className="shadow-2xs self-start sm:self-auto"
        >
          Download PDF Report
        </Button>
      </div>

      {/* Selectors Bar */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
          <div className="md:col-span-5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
              Project
            </label>
            <select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              className="w-full px-3.5 h-[42px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none cursor-pointer"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.title}>
                  {p.title}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-4">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
              Target journal
            </label>
            <select
              value={selectedJournal}
              onChange={(e) => setSelectedJournal(e.target.value)}
              className="w-full px-3.5 h-[42px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none cursor-pointer"
            >
              {journals.map((j) => (
                <option key={j.id} value={j.title}>
                  {j.title}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <Button
              onClick={handleRunCheckAgain}
              isLoading={isRunningCheck}
              leftIcon={<RotateCw className="w-4 h-4" />}
              className="w-full h-[42px]"
            >
              {isRunningCheck ? 'Auditing AST...' : 'Run check again'}
            </Button>
          </div>
        </div>
      </div>

      {/* Top Metric Cards: Verdict & Passed/Failed Counters */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Verdict Banner (6 cols) */}
        <div className="lg:col-span-6 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-red-50 text-red-600 flex items-center justify-center">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-[#14283D]">
                  Not ready for submission
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  2 issues to fix before your next check
                </p>
              </div>
            </div>

            <StatusBadge status="Failed" />
          </div>

          {/* Dual visual progress bar */}
          <div className="mt-6">
            <div className="h-2 w-full bg-slate-100 rounded-full flex overflow-hidden">
              <div className="bg-[#0F766E] w-4/6" title="4 Passed" />
              <div className="bg-red-400 w-2/6" title="2 Failed" />
            </div>
          </div>
        </div>

        {/* Middle Metric: Checks Passed (3 cols) */}
        <div className="lg:col-span-3 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            CHECKS PASSED
          </span>
          <div className="text-4xl font-extrabold text-[#0F766E] mt-3">
            4
          </div>
          <p className="text-xs text-slate-400 mt-1">
            of 6 requirements
          </p>
        </div>

        {/* Right Metric: Checks Failed (3 cols) */}
        <div className="lg:col-span-3 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            CHECKS FAILED
          </span>
          <div className="text-4xl font-extrabold text-red-500 mt-3">
            2
          </div>
          <p className="text-xs text-slate-400 mt-1">
            action required
          </p>
        </div>
      </div>

      {/* Main Breakdown: Checklist Table & Next Steps */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Requirement details (7 cols) */}
        <div className="lg:col-span-7 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h2 className="text-base font-bold text-[#14283D]">Requirement details</h2>
            <span className="text-xs font-medium text-slate-400">6 checks</span>
          </div>

          <div className="divide-y divide-slate-100">
            {complianceReport.checks.map((item) => {
              const isPass = item.status === 'passed';
              return (
                <div key={item.id} className="py-4 flex items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 shrink-0">
                      {isPass ? (
                        <CheckCircle2 className="w-5 h-5 text-[#16A34A]" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-500" />
                      )}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-800 leading-snug">
                        {item.name}
                      </h3>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {item.description}
                      </p>
                    </div>
                  </div>

                  <StatusBadge status={isPass ? 'Passed' : 'Failed'} />
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Your next steps (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-5">
          <h2 className="text-base font-bold text-[#14283D]">Your next steps</h2>

          <div className="space-y-4">
            {/* Step 1 */}
            <div className="p-4 bg-slate-50/70 border border-slate-200/80 rounded-xl space-y-2">
              <span className="inline-block text-[10px] font-bold text-amber-800 bg-[#FEF3C7] px-2.5 py-0.5 rounded-full border border-[#FDE68A]">
                Abstract · 36 words over
              </span>
              <h3 className="font-bold text-sm text-[#14283D]">
                Bring your abstract under 250 words.
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Reduce background detail and combine the methods sentences. Keep the main finding and its implication.
              </p>
              <div className="pt-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => navigate('/summarizer')}
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                  className="text-xs"
                >
                  Review abstract
                </Button>
              </div>
            </div>

            {/* Step 2 */}
            <div className="p-4 bg-slate-50/70 border border-slate-200/80 rounded-xl space-y-2">
              <span className="inline-block text-[10px] font-bold text-red-800 bg-[#FEE2E2] px-2.5 py-0.5 rounded-full border border-[#FECACA]">
                Citation style mismatch
              </span>
              <h3 className="font-bold text-sm text-[#14283D]">
                Switch references to Vancouver.
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Replace author–date citations with numbered references in order of appearance. Review all 38 references.
              </p>
              <div className="pt-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => navigate('/guidelines')}
                  className="text-xs"
                >
                  Open formatting settings
                </Button>
              </div>
            </div>
          </div>

          <p className="text-[11px] text-slate-400 pt-2 border-t border-slate-100">
            Report generated today at 11:08 · urban_green_v4.docx
          </p>
        </div>
      </div>

      {/* Footnote Banner */}
      <div className="p-3.5 bg-[#F0FDF4] border border-[#DCFCE7] rounded-2xl flex items-center gap-2.5 text-xs text-[#166534]">
        <Info className="w-4 h-4 shrink-0 text-[#16A34A]" />
        <span>
          Checks use illustrative journal requirements. Confirm the latest author guidelines before submitting.
        </span>
      </div>
    </div>
  );
};
