import React, { useState } from 'react';
import {
  UploadCloud,
  FileText,
  X,
  Sparkles,
  Copy,
  Download,
  Check,
  Loader2,
  Info,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/StatusBadge';

export const PaperSummarizerPage: React.FC = () => {
  const { addActivity } = useApp();

  const [uploadedFile, setUploadedFile] = useState<{ name: string; size: string; pages: number } | null>({
    name: 'urban_green_v4.pdf',
    size: '2.4 MB',
    pages: 24,
  });

  const [paperText, setPaperText] = useState(
    'We evaluate how urban green infrastructure influences neighborhood heat exposure across 24 cities. Using satellite-derived land surface temperatures and a longitudinal panel model, we find that connected green spaces reduce peak summer temperatures, with the largest benefits in densely built neighborhoods.'
  );

  const [summaryLength, setSummaryLength] = useState('Standard · about 300 words');
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleSummarize = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSummarizing(true);
    setTimeout(() => {
      setIsSummarizing(false);
      addActivity('Paper summarized', 'Urban green infrastructure', 'project');
    }, 1100);
  };

  const handleCopy = () => {
    const fullText = `Urban green infrastructure and heat resilience\nM. Chen, L. Rivera & A. Patel · 2026\n\nOVERVIEW\nThis study examines whether connected urban green spaces reduce neighborhood heat exposure.\n\nKEY FINDINGS\n• Connected green spaces were associated with 1.8°C lower peak surface temperatures.\n• Cooling benefits were strongest in dense neighborhoods.\n• Connectivity was linked to a more consistent cooling effect.`;
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const summaryDoc = `PublishAid Executive Manuscript Summary\nPaper: Urban green infrastructure and heat resilience\nAuthors: M. Chen, L. Rivera & A. Patel\nGenerated: ${new Date().toLocaleDateString()}\n\nOVERVIEW\nThis study examines whether connected urban green spaces reduce neighborhood heat exposure. Across 24 cities, greener and better-connected neighborhoods showed lower peak summer surface temperatures, suggesting that green infrastructure can support local climate adaptation.\n\nKEY FINDINGS\n- Connected green spaces were associated with 1.8°C lower peak surface temperatures after adjustment for built density.\n- Cooling benefits were strongest in dense neighborhoods with limited existing tree cover.\n- Connectivity, not only total green area, was linked to a more consistent cooling effect.\n\nMETHODS\nThe authors combined Landsat-derived surface temperatures, canopy cover and neighborhood characteristics from 2016-2024. A longitudinal panel model with city and year effects assessed associations across 24 cities.\n\nLIMITATIONS\nThe observational design cannot establish causality. Satellite measurements capture surface rather than air temperature and may miss nighttime heat.`;
    const blob = new Blob([summaryDoc], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'urban_green_summary.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
          Understand the paper. Find the signal.
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Turn a full manuscript into a structured, readable research summary.
        </p>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Card: Input (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-5">
          <h2 className="text-base font-bold text-[#14283D]">Add your paper</h2>

          <form onSubmit={handleSummarize} className="space-y-4">
            {/* Dropzone */}
            {!uploadedFile ? (
              <label className="border-2 border-dashed border-slate-200 hover:border-[#0F766E]/50 rounded-2xl p-6 flex flex-col items-center justify-center bg-slate-50/50 hover:bg-[#CCFBF1]/20 cursor-pointer transition-all">
                <UploadCloud className="w-8 h-8 text-[#0F766E] mb-2 stroke-[1.5]" />
                <p className="text-sm font-semibold text-slate-800">
                  Drop a paper or browse files
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  PDF or DOCX · up to 20 MB
                </p>
                <input
                  type="file"
                  accept=".pdf,.docx,.tex"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      const f = e.target.files[0];
                      setUploadedFile({
                        name: f.name,
                        size: `${(f.size / (1024 * 1024)).toFixed(1)} MB`,
                        pages: 18,
                      });
                    }
                  }}
                  className="hidden"
                />
              </label>
            ) : (
              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-[#0F766E]" />
                  <div>
                    <p className="text-xs font-semibold text-slate-800">{uploadedFile.name}</p>
                    <p className="text-[11px] text-slate-400">
                      {uploadedFile.size} · {uploadedFile.pages} pages · Uploaded
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setUploadedFile(null)}
                  className="text-slate-400 hover:text-slate-600 p-1 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            <div className="text-center text-[11px] font-bold uppercase tracking-wider text-slate-400 pt-1">
              OR PASTE PAPER TEXT
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Paper text
              </label>
              <textarea
                rows={6}
                value={paperText}
                onChange={(e) => setPaperText(e.target.value)}
                placeholder="Paste key sections or manuscript text..."
                className="w-full p-3.5 rounded-xl border border-slate-200 text-xs sm:text-sm focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none resize-none leading-relaxed"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Summary length
              </label>
              <select
                value={summaryLength}
                onChange={(e) => setSummaryLength(e.target.value)}
                className="w-full px-3.5 h-[40px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none cursor-pointer"
              >
                <option value="Standard · about 300 words">Standard · about 300 words</option>
                <option value="Concise · about 150 words">Concise · about 150 words</option>
                <option value="Detailed · about 500 words">Detailed · about 500 words</option>
              </select>
            </div>

            <Button
              type="submit"
              size="md"
              isLoading={isSummarizing}
              className="w-full h-[44px] shadow-sm mt-3"
              leftIcon={<Sparkles className="w-4 h-4" />}
            >
              {isSummarizing ? 'Synthesizing Key Claims...' : 'Summarize Paper'}
            </Button>
          </form>

          <p className="text-[11px] text-center text-slate-400 pt-1">
            Your uploaded manuscript is only used to generate this summary.
          </p>
        </div>

        {/* Right Card: Output (7 cols) */}
        <div className="lg:col-span-7 bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-2xs space-y-6">
          {/* Top Bar */}
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#0F766E] bg-[#DCFCE7] px-3 py-1 rounded-full border border-[#BBF7D0]">
              Summary complete
            </span>

            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={handleCopy}
                leftIcon={copied ? <Check className="w-3.5 h-3.5 text-[#0F766E]" /> : <Copy className="w-3.5 h-3.5" />}
              >
                {copied ? 'Copied' : 'Copy'}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={handleDownload}
                leftIcon={<Download className="w-3.5 h-3.5" />}
              >
                Download
              </Button>
            </div>
          </div>

          {/* Title & Metadata */}
          <div>
            <h2 className="text-xl sm:text-2xl font-extrabold text-[#14283D] tracking-tight leading-snug">
              Urban green infrastructure and heat resilience
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              M. Chen, L. Rivera & A. Patel · Research manuscript · 2026
            </p>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <span className="bg-[#CCFBF1] text-[#0F766E] text-xs font-semibold px-2.5 py-0.5 rounded-full border border-[#99F6E4]">
                Environmental science
              </span>
              <span className="bg-slate-100 text-slate-600 text-xs font-medium px-2.5 py-0.5 rounded-full">
                3 min read
              </span>
              <span className="bg-slate-100 text-slate-600 text-xs font-medium px-2.5 py-0.5 rounded-full">
                24 pages analyzed
              </span>
            </div>
          </div>

          <div className="h-[1px] bg-slate-100" />

          {/* Structured Sections */}
          <div className="space-y-5 text-xs sm:text-sm">
            {/* Section 1: Overview */}
            <div>
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                OVERVIEW
              </h3>
              <p className="text-slate-700 leading-relaxed">
                This study examines whether connected urban green spaces reduce neighborhood heat exposure. Across 24 cities, greener and better-connected neighborhoods showed lower peak summer surface temperatures, suggesting that green infrastructure can support local climate adaptation.
              </p>
            </div>

            {/* Section 2: Key Findings */}
            <div>
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                KEY FINDINGS
              </h3>
              <ul className="space-y-2 text-slate-700">
                <li className="flex items-start gap-2.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#0F766E] mt-2 shrink-0" />
                  <span className="leading-relaxed">
                    Connected green spaces were associated with 1.8°C lower peak surface temperatures after adjustment for built density.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#0F766E] mt-2 shrink-0" />
                  <span className="leading-relaxed">
                    Cooling benefits were strongest in dense neighborhoods with limited existing tree cover.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#0F766E] mt-2 shrink-0" />
                  <span className="leading-relaxed">
                    Connectivity, not only total green area, was linked to a more consistent cooling effect.
                  </span>
                </li>
              </ul>
            </div>

            {/* Section 3: Methods */}
            <div>
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                METHODS
              </h3>
              <p className="text-slate-700 leading-relaxed">
                The authors combined Landsat-derived surface temperatures, canopy cover and neighborhood characteristics from 2016–2024. A longitudinal panel model with city and year effects assessed associations across 24 cities, with sensitivity analyses for land use and seasonality.
              </p>
            </div>

            {/* Section 4: Limitations */}
            <div>
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                LIMITATIONS
              </h3>
              <p className="text-slate-700 leading-relaxed">
                The observational design cannot establish causality. Satellite measurements capture surface rather than air temperature and may miss nighttime heat. Results may not generalize to cities outside the sampled climate zones.
              </p>
            </div>
          </div>

          {/* AI Banner */}
          <div className="p-3 bg-[#CCFBF1]/30 border border-[#99F6E4] rounded-xl flex items-center gap-2.5 text-xs text-[#0F766E]">
            <Sparkles className="w-4 h-4 shrink-0 text-[#0F766E]" />
            <span>
              AI-generated summary. Check key claims, numerical results and interpretations against the original paper.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
