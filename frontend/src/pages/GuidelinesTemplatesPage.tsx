import React, { useState } from 'react';
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
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';

export const GuidelinesTemplatesPage: React.FC = () => {
  const { addActivity } = useApp();

  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [publisher, setPublisher] = useState('Meridian Science / Journal of Sustainable Systems');
  const [guidelinesText, setGuidelinesText] = useState(
    'Manuscripts must not exceed 8,000 words excluding references. Abstract limit is strictly 250 words. References must follow Vancouver numbered format [1], [2]. Double-column layout with 10pt font, standard 20mm margins. Mandatory declarations: Funding, Conflict of Interest, and Author Contributions.'
  );

  // Formatting settings state
  const [columnLayout, setColumnLayout] = useState('Double column');
  const [lineSpacing, setLineSpacing] = useState('Single');
  const [margins, setMargins] = useState({ top: '20mm', bottom: '20mm', left: '20mm', right: '20mm' });
  const [fontFamily, setFontFamily] = useState('Default (publisher recommended)');
  const [fontSizes, setFontSizes] = useState({ title: '14pt', text: '10pt', figCaption: '8.5pt', tblCaption: '8.5pt' });
  const [referencingStyle, setReferencingStyle] = useState('Vancouver');
  const [keywordSeparator, setKeywordSeparator] = useState('Semicolon (;)');
  const [documentClass, setDocumentClass] = useState('sn-jnl (LaTeX2e)');
  const [isSaved, setIsSaved] = useState(false);

  const handleSaveDraft = () => {
    setIsSaved(true);
    addActivity('Guideline draft saved', publisher, 'journal');
    setTimeout(() => setIsSaved(false), 3000);
  };

  const handleDownloadTemplate = () => {
    addActivity('LaTeX template generated', `${referencingStyle} · ${columnLayout}`, 'conversion');
    // Create mock .tex download
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

  return (
    <div className="space-y-6">
      {/* Page Title & Stepper */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
            Guidelines & Templates
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Prepare your manuscript with publisher-specific formatting settings.
          </p>
        </div>

        {/* Stepper Progress Indicator */}
        <div className="flex flex-col items-end gap-1.5 self-start sm:self-auto">
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full transition-colors ${
                currentStep >= 1 ? 'bg-[#0F766E]' : 'bg-slate-300'
              }`}
            />
            <span
              className={`w-8 h-0.5 transition-colors ${
                currentStep >= 2 ? 'bg-[#0F766E]' : 'bg-slate-200'
              }`}
            />
            <span
              className={`w-2.5 h-2.5 rounded-full transition-colors ${
                currentStep >= 2 ? 'bg-[#0F766E]' : 'bg-slate-300'
              }`}
            />
            <span
              className={`w-8 h-0.5 transition-colors ${
                currentStep >= 3 ? 'bg-[#0F766E]' : 'bg-slate-200'
              }`}
            />
            <span
              className={`w-2.5 h-2.5 rounded-full transition-colors ${
                currentStep === 3 ? 'bg-[#0F766E]' : 'bg-slate-300'
              }`}
            />
          </div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            {currentStep === 1 && 'STEP 1 OF 3: GUIDELINES'}
            {currentStep === 2 && 'STEP 2 OF 3: TECHNICAL SPECS'}
            {currentStep === 3 && 'STEP 3 OF 3: MANUSCRIPT'}
          </span>
        </div>
      </div>

      {/* Main Container with Sidebar Tabs on Left and Content on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Sub-navigation (3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-white rounded-2xl p-3 border border-slate-200/80 shadow-2xs space-y-1">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 py-1">
              SUBMISSION SETUP
            </p>

            <button
              onClick={() => setCurrentStep(1)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                currentStep === 1
                  ? 'bg-[#CCFBF1] text-[#0F766E]'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <Building2 className="w-4 h-4 stroke-[2]" />
              <span>Publisher</span>
            </button>

            <button
              onClick={() => setCurrentStep(2)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                currentStep === 2
                  ? 'bg-[#CCFBF1] text-[#0F766E]'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <Sliders className="w-4 h-4 stroke-[2]" />
              <span>Settings</span>
            </button>

            <button
              onClick={() => setCurrentStep(3)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                currentStep === 3
                  ? 'bg-[#CCFBF1] text-[#0F766E]'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <FileText className="w-4 h-4 stroke-[2]" />
              <span>Manuscript</span>
            </button>
          </div>

          {/* Save Draft Button */}
          <div className="space-y-1.5">
            <Button
              variant="secondary"
              onClick={handleSaveDraft}
              leftIcon={<Save className="w-4 h-4 text-[#0F766E]" />}
              className="w-full text-xs shadow-2xs"
            >
              {isSaved ? 'Draft Saved!' : 'Save Draft'}
            </Button>
            <p className="text-[11px] text-center text-slate-400">
              Draft saved just now
            </p>
          </div>
        </div>

        {/* Right Form Card (9 cols) */}
        <div className="lg:col-span-9 space-y-4">
          {/* STEP 1: PUBLISHER & SMART GUIDELINES */}
          {currentStep === 1 && (
            <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-2xs space-y-6 animate-fade-in">
              <div>
                <h2 className="text-xl font-bold text-[#14283D]">New submission</h2>
                <p className="text-xs text-slate-500 mt-1">
                  Choose the target publisher to load its formatting rules.
                </p>
              </div>

              <div className="space-y-5">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                    Publisher *
                  </label>
                  <select
                    value={publisher}
                    onChange={(e) => setPublisher(e.target.value)}
                    className="w-full px-4 h-[44px] rounded-xl border border-slate-200 text-sm bg-white focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none cursor-pointer"
                  >
                    <option value="Meridian Science / Journal of Sustainable Systems">
                      Meridian Science — Journal of Sustainable Systems
                    </option>
                    <option value="Atlas Academic / Urban Climate & Society">
                      Atlas Academic — Urban Climate & Society
                    </option>
                    <option value="Northstar Press / Environmental Research Advances">
                      Northstar Press — Environmental Research Advances
                    </option>
                    <option value="IEEE / IEEE Access">
                      IEEE — IEEE Access
                    </option>
                    <option value="Elsevier / Cities">
                      Elsevier — Cities
                    </option>
                    <option value="Springer Nature / Scientific Reports">
                      Springer Nature — Scientific Reports
                    </option>
                  </select>
                </div>

                <div className="pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Sparkles className="w-4 h-4 text-[#0F766E]" />
                    <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                      Smart Guidelines
                    </h3>
                  </div>
                  <label className="block text-xs text-slate-500 mb-2">
                    Our AI will automatically fill the technical specs based on the text provided.
                  </label>

                  <textarea
                    rows={6}
                    value={guidelinesText}
                    onChange={(e) => setGuidelinesText(e.target.value)}
                    placeholder="Paste the text from the publisher's website or author instructions URL here..."
                    className="w-full p-4 rounded-xl border border-slate-200 text-xs sm:text-sm focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none resize-none leading-relaxed"
                  />
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                <span className="text-xs text-slate-400">Settings are automatically saved as you edit.</span>
                <Button
                  onClick={() => setCurrentStep(2)}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  Continue
                </Button>
              </div>
            </div>
          )}

          {/* STEP 2: FORMATTING SETTINGS / TECHNICAL SPECS */}
          {currentStep === 2 && (
            <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-2xs space-y-6 animate-fade-in">
              <div>
                <h2 className="text-xl font-bold text-[#14283D]">Formatting settings</h2>
                <p className="text-xs text-slate-500 mt-1">
                  Fine-tune layout, typography, and citation rules extracted from guidelines.
                </p>
              </div>

              {/* Group 1: Page Layout & Spacing */}
              <div className="space-y-4 pt-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-100 pb-1.5">
                  Page Layout & Spacing
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Column Layout
                    </label>
                    <select
                      value={columnLayout}
                      onChange={(e) => setColumnLayout(e.target.value)}
                      className="w-full px-3.5 h-[40px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none"
                    >
                      <option value="Single column">Single column</option>
                      <option value="Double column">Double column</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Line Spacing
                    </label>
                    <select
                      value={lineSpacing}
                      onChange={(e) => setLineSpacing(e.target.value)}
                      className="w-full px-3.5 h-[40px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none"
                    >
                      <option value="Single">Single (1.0)</option>
                      <option value="1.5 lines">1.5 lines</option>
                      <option value="Double">Double (2.0)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Margins (mm)
                  </label>
                  <div className="grid grid-cols-4 gap-3">
                    {['T', 'B', 'L', 'R'].map((side) => (
                      <div key={side}>
                        <span className="text-[11px] font-bold text-slate-400 block mb-0.5">{side}</span>
                        <input
                          type="text"
                          defaultValue="20mm"
                          className="w-full px-2.5 h-[36px] rounded-lg border border-slate-200 text-xs text-center focus:border-[#0F766E] outline-none"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Group 2: Typography Defaults */}
              <div className="space-y-4 pt-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-100 pb-1.5">
                  Typography Defaults
                </h3>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Font Family
                  </label>
                  <select
                    value={fontFamily}
                    onChange={(e) => setFontFamily(e.target.value)}
                    className="w-full px-3.5 h-[40px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none"
                  >
                    <option value="Default (publisher recommended)">Default (publisher recommended)</option>
                    <option value="Times New Roman">Times New Roman</option>
                    <option value="Computer Modern (LaTeX standard)">Computer Modern (LaTeX standard)</option>
                    <option value="Arial / Helvetica">Arial / Helvetica</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Font Sizes (pt)
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div>
                      <span className="text-[11px] font-semibold text-slate-500 block mb-0.5">Title</span>
                      <select className="w-full px-2 h-[36px] rounded-lg border border-slate-200 text-xs bg-white">
                        <option>14pt</option>
                        <option>16pt</option>
                        <option>18pt</option>
                      </select>
                    </div>
                    <div>
                      <span className="text-[11px] font-semibold text-slate-500 block mb-0.5">Text</span>
                      <select className="w-full px-2 h-[36px] rounded-lg border border-slate-200 text-xs bg-white">
                        <option>10pt</option>
                        <option>11pt</option>
                        <option>12pt</option>
                      </select>
                    </div>
                    <div>
                      <span className="text-[11px] font-semibold text-slate-500 block mb-0.5">Fig Caption</span>
                      <select className="w-full px-2 h-[36px] rounded-lg border border-slate-200 text-xs bg-white">
                        <option>8.5pt</option>
                        <option>9pt</option>
                      </select>
                    </div>
                    <div>
                      <span className="text-[11px] font-semibold text-slate-500 block mb-0.5">Tbl Caption</span>
                      <select className="w-full px-2 h-[36px] rounded-lg border border-slate-200 text-xs bg-white">
                        <option>8.5pt</option>
                        <option>9pt</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              {/* Group 3: Referencing & Content */}
              <div className="space-y-4 pt-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-100 pb-1.5">
                  Referencing & Content
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Referencing Style
                    </label>
                    <select
                      value={referencingStyle}
                      onChange={(e) => setReferencingStyle(e.target.value)}
                      className="w-full px-3.5 h-[40px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none"
                    >
                      <option value="Vancouver">Vancouver (Numbered brackets [1])</option>
                      <option value="APA 7">APA 7th Edition (Author, Year)</option>
                      <option value="IEEE">IEEE Reference Style</option>
                      <option value="Harvard">Harvard Referencing</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Keyword Separator
                    </label>
                    <select
                      value={keywordSeparator}
                      onChange={(e) => setKeywordSeparator(e.target.value)}
                      className="w-full px-3.5 h-[40px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none"
                    >
                      <option value="Semicolon (;)">Semicolon (;)</option>
                      <option value="Comma (,)">Comma (,)</option>
                      <option value="Bullet (•)">Bullet (•)</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Footer navigation */}
              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                <Button
                  variant="secondary"
                  onClick={() => setCurrentStep(1)}
                  leftIcon={<ArrowLeft className="w-4 h-4" />}
                >
                  Back to Publisher
                </Button>
                <Button
                  onClick={() => setCurrentStep(3)}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  Continue to Manuscript
                </Button>
              </div>
            </div>
          )}

          {/* STEP 3: MANUSCRIPT & TEMPLATE SYNTHESIS */}
          {currentStep === 3 && (
            <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-2xs space-y-6 animate-fade-in">
              <div>
                <h2 className="text-xl font-bold text-[#14283D]">Ready to generate template</h2>
                <p className="text-xs text-slate-500 mt-1">
                  PublishAid compiled a custom LaTeX package tailored to the extracted rules.
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
                  onClick={() => setCurrentStep(2)}
                  leftIcon={<ArrowLeft className="w-4 h-4" />}
                >
                  Back to Settings
                </Button>
                <Button
                  onClick={() => alert('Template preferences linked to your active manuscript workspace.')}
                  leftIcon={<CheckCircle2 className="w-4 h-4" />}
                >
                  Confirm & Apply
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
