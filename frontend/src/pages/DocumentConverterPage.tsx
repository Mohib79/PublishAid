import React, { useState } from 'react';
import {
  UploadCloud,
  FileText,
  RefreshCw,
  Download,
  Check,
  CheckCircle2,
  FolderArchive,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/StatusBadge';

export const DocumentConverterPage: React.FC = () => {
  const { conversions, addConversion } = useApp();

  const [direction, setDirection] = useState<'WordToLatex' | 'LatexToWord'>('WordToLatex');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preserveElements, setPreserveElements] = useState(true);
  const [conversionState, setConversionState] = useState<'idle' | 'converting' | 'complete'>('complete');
  const [convertedResult, setConvertedResult] = useState<{
    zipName: string;
    size: string;
    pages: number;
    refs: number;
    figs: number;
  }>({
    zipName: 'urban_green_v4_latex.zip',
    size: '2.2 MB',
    pages: 24,
    refs: 38,
    figs: 6,
  });

  const handleConvert = (e: React.FormEvent) => {
    e.preventDefault();
    setConversionState('converting');
    setTimeout(() => {
      const srcFormat = direction === 'WordToLatex' ? 'DOCX' : 'TEX';
      const tgtFormat = direction === 'WordToLatex' ? 'TEX' : 'DOCX';
      const filePayload = selectedFile || { name: 'urban_green_v4.docx', size: '2.4 MB' };
      addConversion(filePayload, srcFormat, tgtFormat);
      setConvertedResult({
        zipName: selectedFile ? `${selectedFile.name.replace(/\.[^/.]+$/, '')}_converted.zip` : 'urban_green_v4_latex.zip',
        size: '2.2 MB',
        pages: 24,
        refs: 38,
        figs: 6,
      });
      setConversionState('complete');
    }, 1200);
  };

  const handleDownloadZip = () => {
    const dummyLatexZip = `PublishAid Converted Package Archive\nOriginal: ${convertedResult.zipName}\nContains: main.tex, references.bib, figures/`;
    const blob = new Blob([dummyLatexZip], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = convertedResult.zipName;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
          Switch formats. Keep your focus.
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Convert between Word and LaTeX without rebuilding your manuscript.
        </p>
      </div>

      {/* Grid: Converter Form & Result */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Left Card: Upload */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-5">
          <h2 className="text-base font-bold text-[#14283D]">
            {conversionState === 'complete' ? 'Start another conversion' : 'Upload your document'}
          </h2>

          <form onSubmit={handleConvert} className="space-y-4">
            {/* Direction Toggle Pills */}
            <div className="p-1 bg-slate-100 rounded-xl flex items-center">
              <button
                type="button"
                onClick={() => setDirection('WordToLatex')}
                className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  direction === 'WordToLatex'
                    ? 'bg-white text-[#0F766E] shadow-2xs'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Word to LaTeX
              </button>
              <button
                type="button"
                onClick={() => setDirection('LatexToWord')}
                className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  direction === 'LatexToWord'
                    ? 'bg-white text-[#0F766E] shadow-2xs'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                LaTeX to Word
              </button>
            </div>

            {/* Dropzone */}
            <label className="border-2 border-dashed border-slate-200 hover:border-[#0F766E]/50 rounded-2xl p-8 flex flex-col items-center justify-center bg-slate-50/50 hover:bg-[#CCFBF1]/20 cursor-pointer transition-all">
              <UploadCloud className="w-8 h-8 text-[#0F766E] mb-2 stroke-[1.5]" />
              <p className="text-sm font-semibold text-slate-800">
                {selectedFile ? selectedFile.name : 'Drop your manuscript here'}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                {direction === 'WordToLatex' ? 'DOCX file · up to 20 MB' : 'TEX file + optional .bib · up to 20 MB'}
              </p>
              <div className="mt-3 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 shadow-2xs">
                + Browse files
              </div>
              <input
                type="file"
                accept={direction === 'WordToLatex' ? '.docx' : '.tex,.bib'}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setSelectedFile(e.target.files[0]);
                  }
                }}
                className="hidden"
              />
            </label>

            <label className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={preserveElements}
                onChange={(e) => setPreserveElements(e.target.checked)}
                className="w-4 h-4 rounded text-[#0F766E] border-slate-300 focus:ring-[#0F766E]"
              />
              <span className="font-medium">Preserve references, tables and equations</span>
            </label>

            <Button
              type="submit"
              size="md"
              isLoading={conversionState === 'converting'}
              className="w-full h-[44px] shadow-sm"
              leftIcon={<RefreshCw className="w-4 h-4" />}
            >
              {conversionState === 'converting' ? 'Converting via AST...' : 'Convert Document'}
            </Button>
          </form>

          <p className="text-[11px] text-center text-slate-400 pt-1">
            Files are processed securely and automatically removed after 24 hours.
          </p>
        </div>

        {/* Right Card: Output */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-5">
          {conversionState === 'idle' && (
            <div className="p-12 flex flex-col items-center justify-center text-center min-h-[360px]">
              <div className="w-14 h-14 rounded-full bg-[#CCFBF1] text-[#0F766E] flex items-center justify-center mb-3">
                <FileText className="w-7 h-7" />
              </div>
              <h3 className="text-base font-bold text-[#14283D]">Ready for a new format?</h3>
              <p className="text-xs text-slate-500 max-w-xs mt-1">
                Upload your manuscript to convert between Word and LaTeX with lossless AST transformation.
              </p>
              <span className="mt-4 px-3 py-1 rounded-full text-xs bg-slate-100 text-slate-500">
                No file selected
              </span>
            </div>
          )}

          {conversionState === 'converting' && (
            <div className="p-12 flex flex-col items-center justify-center text-center min-h-[360px]">
              <Loader2 className="w-10 h-10 text-[#0F766E] animate-spin mb-3" />
              <h3 className="text-base font-bold text-[#14283D]">Converting document syntax...</h3>
              <p className="text-xs text-slate-500 max-w-xs mt-1">
                Mapping OpenXML document elements into Pandoc / LaTeX AST nodes, extracting equations and tables.
              </p>
            </div>
          )}

          {conversionState === 'complete' && (
            <div className="space-y-5 animate-fade-in">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold text-[#14283D]">Your document is ready</h2>
                <StatusBadge status="Completed" />
              </div>

              {/* Graphic Banner */}
              <div className="bg-[#CCFBF1]/40 border border-[#99F6E4] rounded-2xl p-8 flex flex-col items-center justify-center text-center">
                <div className="w-12 h-12 rounded-xl bg-white text-[#0F766E] flex items-center justify-center shadow-2xs mb-3 border border-[#99F6E4]/50">
                  <CheckCircle2 className="w-6 h-6 stroke-[2]" />
                </div>
                <h3 className="font-extrabold text-base text-[#0D5E4B]">
                  A new format. The same research.
                </h3>
              </div>

              {/* Converted File Card */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-[#CCFBF1] text-[#0F766E] flex items-center justify-center">
                    <FolderArchive className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-800">{convertedResult.zipName}</h4>
                    <p className="text-[11px] text-slate-500">
                      LaTeX source, bibliography & figures · {convertedResult.size}
                    </p>
                  </div>
                </div>
              </div>

              {/* Status Note */}
              <div className="p-3 bg-[#F0FDF4] border border-[#DCFCE7] rounded-xl flex items-center gap-2 text-xs text-[#166534]">
                <Check className="w-4 h-4 text-[#16A34A] shrink-0" />
                <span>
                  Converted today at 10:42 · {convertedResult.pages} pages, {convertedResult.refs} references and {convertedResult.figs} figures preserved.
                </span>
              </div>

              {/* Download Action */}
              <Button
                onClick={handleDownloadZip}
                leftIcon={<Download className="w-4 h-4" />}
                className="w-full h-[44px] shadow-sm"
              >
                Download ZIP
              </Button>

              <p className="text-[11px] text-center text-slate-400">
                Review the output before submitting to your journal.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* History */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-[#14283D]">Conversion history</h2>
          <span className="text-xs font-semibold text-slate-500 hover:text-[#0F766E] cursor-pointer">
            View all conversions →
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                <th className="pb-3">DOCUMENT</th>
                <th className="pb-3">CONVERSION</th>
                <th className="pb-3">DATE</th>
                <th className="pb-3">STATUS</th>
                <th className="pb-3 text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {conversions.map((conv) => (
                <tr key={conv.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-3.5 pr-4">
                    <div className="flex items-center gap-2.5">
                      <FileText className="w-4 h-4 text-[#0F766E]" />
                      <div>
                        <p className="font-semibold text-slate-800">{conv.fileName}</p>
                        <p className="text-[10px] text-slate-400">{conv.fileSize}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 font-medium text-slate-600">
                    {conv.sourceFormat === 'DOCX' ? 'Word → LaTeX' : 'LaTeX → Word'}
                  </td>
                  <td className="py-3.5 text-slate-400">{conv.date}</td>
                  <td className="py-3.5">
                    <StatusBadge status={conv.status} />
                  </td>
                  <td className="py-3.5 text-right">
                    <button
                      onClick={handleDownloadZip}
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
