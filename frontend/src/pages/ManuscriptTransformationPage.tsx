import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  X,
  ArrowRight,
  Check,
  AlertTriangle,
  Download,
  ShieldCheck,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/StatusBadge';

export const ManuscriptTransformationPage: React.FC = () => {
  const navigate = useNavigate();
  const { transformations, addTransformation, activeProject } = useApp();

  const [uploadedFile, setUploadedFile] = useState<{ name: string; size: string } | null>({
    name: 'urban_green_v4.docx',
    size: '2.4 MB',
  });
  const [targetJournal, setTargetJournal] = useState('Urban Climate & Society');
  const [applyTemplate, setApplyTemplate] = useState(true);
  const [reformatRefs, setReformatRefs] = useState(true);
  const [adjustFigures, setAdjustFigures] = useState(true);
  const [isTransforming, setIsTransforming] = useState(false);
  const [hasResult, setHasResult] = useState(true);

  const handleTransform = (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadedFile) {
      alert('Please upload a source manuscript file (.docx or .tex)');
      return;
    }
    setIsTransforming(true);
    setTimeout(() => {
      addTransformation(uploadedFile.name, targetJournal);
      setIsTransforming(false);
      setHasResult(true);
    }, 1200);
  };

  const handleDownload = () => {
    const dummyData = `Transformed manuscript adapted for ${targetJournal}\nSource: ${uploadedFile?.name}\nTimestamp: ${new Date().toISOString()}`;
    const blob = new Blob([dummyData], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transformed_${uploadedFile?.name || 'manuscript.docx'}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
          Reformat for your next journal.
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Adapt your manuscript to a new journal's template without starting over.
        </p>
      </div>

      {/* Main Grid: Set up Transformation & Transformation Result */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Left Card: Set up transformation */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-5">
          <h2 className="text-base font-bold text-[#14283D]">Set up transformation</h2>

          <form onSubmit={handleTransform} className="space-y-4">
            {/* File Dropzone */}
            {!uploadedFile ? (
              <label className="border-2 border-dashed border-slate-200 hover:border-[#0F766E]/50 rounded-2xl p-7 flex flex-col items-center justify-center bg-slate-50/50 hover:bg-[#CCFBF1]/20 cursor-pointer transition-all">
                <UploadCloud className="w-8 h-8 text-[#0F766E] mb-2 stroke-[1.5]" />
                <p className="text-sm font-semibold text-slate-800">
                  Drop your manuscript here
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  DOCX or TEX · up to 20 MB
                </p>
                <input
                  type="file"
                  accept=".docx,.tex"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      const f = e.target.files[0];
                      setUploadedFile({
                        name: f.name,
                        size: `${(f.size / (1024 * 1024)).toFixed(1)} MB`,
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
                    <p className="text-[11px] text-slate-400">{uploadedFile.size}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setUploadedFile(null)}
                  className="text-slate-400 hover:text-slate-600 p-1"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Target Journal Selection */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Target journal
                </label>
                <span className="text-[10px] font-bold text-[#0F766E] bg-[#DCFCE7] px-2 py-0.5 rounded-full border border-[#BBF7D0]">
                  Template ready
                </span>
              </div>
              <select
                value={targetJournal}
                onChange={(e) => setTargetJournal(e.target.value)}
                className="w-full px-3.5 h-[42px] rounded-xl border border-slate-200 text-xs sm:text-sm bg-white focus:border-[#0F766E] outline-none cursor-pointer"
              >
                <option value="Urban Climate & Society">Urban Climate & Society (Atlas Academic)</option>
                <option value="Journal of Sustainable Systems">Journal of Sustainable Systems (Meridian Science)</option>
                <option value="Environmental Research Advances">Environmental Research Advances (Northstar Press)</option>
              </select>
            </div>

            {/* Checkbox Options */}
            <div className="space-y-2.5 pt-2">
              <label className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={applyTemplate}
                  onChange={(e) => setApplyTemplate(e.target.checked)}
                  className="w-4 h-4 rounded text-[#0F766E] border-slate-300 focus:ring-[#0F766E]"
                />
                <span className="font-medium">Apply journal template</span>
              </label>

              <label className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={reformatRefs}
                  onChange={(e) => setReformatRefs(e.target.checked)}
                  className="w-4 h-4 rounded text-[#0F766E] border-slate-300 focus:ring-[#0F766E]"
                />
                <span className="font-medium">Reformat references</span>
              </label>

              <label className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={adjustFigures}
                  onChange={(e) => setAdjustFigures(e.target.checked)}
                  className="w-4 h-4 rounded text-[#0F766E] border-slate-300 focus:ring-[#0F766E]"
                />
                <span className="font-medium">Adjust figures and tables</span>
              </label>
            </div>

            {/* Action */}
            <Button
              type="submit"
              size="md"
              isLoading={isTransforming}
              className="w-full h-[44px] shadow-sm mt-3"
            >
              {isTransforming ? 'Transforming Document...' : 'Transform Manuscript'}
            </Button>
          </form>
        </div>

        {/* Right Card: Transformation result */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-[#14283D]">Transformation result</h2>
            <StatusBadge status="Completed" />
          </div>

          {/* Visual Before & After Preview */}
          <div className="bg-[#F0FDF4]/50 border border-[#DCFCE7] rounded-2xl p-6 flex items-center justify-center gap-6">
            {/* Original Preview representation */}
            <div className="flex flex-col items-center">
              <div className="w-28 h-36 bg-white rounded-lg shadow-sm border border-slate-200 p-2.5 space-y-1">
                <div className="h-1.5 w-16 bg-slate-300 rounded mb-1" />
                <div className="h-1 w-10 bg-slate-200 rounded mb-2" />
                <div className="h-1 w-full bg-slate-200 rounded" />
                <div className="h-1 w-full bg-slate-200 rounded" />
                <div className="h-1 w-5/6 bg-slate-200 rounded" />
                <div className="h-1 w-full bg-slate-200 rounded" />
                <div className="h-1 w-4/5 bg-slate-200 rounded" />
                <div className="h-1 w-full bg-slate-200 rounded" />
                <div className="h-1 w-3/4 bg-slate-200 rounded" />
              </div>
              <span className="text-[11px] text-slate-500 font-medium mt-2">Original</span>
            </div>

            {/* Arrow */}
            <div className="w-8 h-8 rounded-full bg-emerald-100 text-[#0F766E] flex items-center justify-center shrink-0">
              <ArrowRight className="w-4 h-4" />
            </div>

            {/* Journal Format Preview representation */}
            <div className="flex flex-col items-center">
              <div className="w-28 h-36 bg-white rounded-lg shadow-sm border border-[#0F766E]/40 p-2.5 space-y-1 relative overflow-hidden">
                <div className="h-1 w-full bg-[#0F766E] rounded mb-1.5" />
                <div className="grid grid-cols-2 gap-1.5">
                  <div className="space-y-1">
                    <div className="h-1 w-full bg-slate-200 rounded" />
                    <div className="h-1 w-full bg-slate-200 rounded" />
                    <div className="h-1 w-4/5 bg-slate-200 rounded" />
                    <div className="h-1 w-full bg-slate-200 rounded" />
                  </div>
                  <div className="space-y-1">
                    <div className="h-1 w-full bg-slate-200 rounded" />
                    <div className="h-1 w-3/4 bg-slate-200 rounded" />
                    <div className="h-1 w-full bg-slate-200 rounded" />
                    <div className="h-1 w-5/6 bg-slate-200 rounded" />
                  </div>
                </div>
              </div>
              <span className="text-[11px] text-[#0F766E] font-bold mt-2">Journal format</span>
            </div>
          </div>

          {/* Changes Applied Checklist */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Changes applied
            </h3>

            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2 text-slate-700">
                <div className="w-4 h-4 rounded-full bg-[#DCFCE7] text-[#15803D] flex items-center justify-center">
                  <Check className="w-2.5 h-2.5 stroke-[3]" />
                </div>
                <span>Single to double column</span>
              </div>

              <div className="flex items-center gap-2 text-slate-700">
                <div className="w-4 h-4 rounded-full bg-[#DCFCE7] text-[#15803D] flex items-center justify-center">
                  <Check className="w-2.5 h-2.5 stroke-[3]" />
                </div>
                <span>Citation style changed to APA</span>
              </div>

              <div className="flex items-center gap-2 text-slate-700">
                <div className="w-4 h-4 rounded-full bg-[#DCFCE7] text-[#15803D] flex items-center justify-center">
                  <Check className="w-2.5 h-2.5 stroke-[3]" />
                </div>
                <span>Margins and fonts updated</span>
              </div>

              <div className="flex items-center gap-2 text-amber-700">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <span className="font-semibold">4 items need manual review</span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="pt-2 flex flex-col sm:flex-row items-center gap-3">
            <Button
              onClick={handleDownload}
              leftIcon={<Download className="w-4 h-4" />}
              className="w-full sm:flex-1 shadow-sm"
            >
              Download Manuscript
            </Button>
            <Button
              variant="secondary"
              onClick={() => navigate('/compliance')}
              leftIcon={<ShieldCheck className="w-4 h-4 text-[#0F766E]" />}
              className="w-full sm:flex-1"
            >
              Run Compliance Check
            </Button>
          </div>

          <p className="text-[11px] text-center text-slate-400">
            Review the output before submitting.
          </p>
        </div>
      </div>

      {/* Transformation History Table */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-4">
        <h2 className="text-base font-bold text-[#14283D]">Transformation history</h2>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                <th className="pb-3">MANUSCRIPT</th>
                <th className="pb-3">TARGET JOURNAL</th>
                <th className="pb-3">DATE</th>
                <th className="pb-3">STATUS</th>
                <th className="pb-3 text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {transformations.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-3.5 pr-4">
                    <div className="flex items-center gap-2.5">
                      <FileText className="w-4 h-4 text-[#0F766E]" />
                      <div>
                        <p className="font-semibold text-slate-800">{item.manuscriptName}</p>
                        <p className="text-[10px] text-slate-400">{item.fileSize}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 font-medium text-slate-600">{item.targetJournal}</td>
                  <td className="py-3.5 text-slate-400">{item.date}</td>
                  <td className="py-3.5">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="py-3.5 text-right">
                    <button
                      onClick={handleDownload}
                      className="text-slate-400 hover:text-[#0F766E] p-1.5 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
