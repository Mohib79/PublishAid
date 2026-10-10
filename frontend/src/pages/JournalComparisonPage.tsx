import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, X, Check, Bookmark, Info, CheckCircle2 } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/StatusBadge';

export const JournalComparisonPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    journals,
    selectedCompareJournalIds,
    toggleCompareJournal,
    activeProject,
    addActivity,
  } = useApp();

  const [selectedTargetId, setSelectedTargetId] = useState<string>('jrn_01');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const comparedJournals = journals.filter((j) =>
    selectedCompareJournalIds.includes(j.id)
  );

  const handleSelectJournal = (journalId: string, journalTitle: string) => {
    setSelectedTargetId(journalId);
    addActivity('Target journal assigned', journalTitle, 'journal');
    alert(`"${journalTitle}" has been set as the primary target journal for "${activeProject?.title || 'active project'}".`);
  };

  return (
    <div className="space-y-6">
      {/* Page Title & Action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
            Compare your shortlist.
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            See the trade-offs clearly. Choose the journal that works for your research.
          </p>
        </div>

        <Button
          variant="secondary"
          onClick={() => setIsAddModalOpen(true)}
          leftIcon={<Plus className="w-4 h-4 text-[#0F766E]" />}
          className="shadow-2xs self-start sm:self-auto"
        >
          Add journal
        </Button>
      </div>

      {/* Sub-bar */}
      <div className="flex items-center justify-between text-xs text-slate-500 font-medium px-1">
        <div>
          <span>For: </span>
          <span className="font-semibold text-slate-800">
            {activeProject?.title || 'Urban green infrastructure and heat resilience'}
          </span>
        </div>
        <div className="text-slate-400">
          {comparedJournals.length} of 4 journals selected
        </div>
      </div>

      {/* Side-by-Side Comparison Matrix */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[760px]">
            {/* Header Row */}
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/50">
                <th className="p-5 w-[180px] text-xs font-bold uppercase tracking-wider text-slate-400 align-top">
                  COMPARE BY
                </th>
                {comparedJournals.map((journal) => (
                  <th key={journal.id} className="p-5 align-top min-w-[240px] border-l border-slate-100">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1.5">
                        {journal.matchTag ? (
                          <span className="bg-[#CCFBF1] text-[#0F766E] text-[10px] font-bold px-2.5 py-0.5 rounded-full border border-[#99F6E4] inline-block">
                            {journal.matchTag}
                          </span>
                        ) : (
                          <StatusBadge status={journal.quartile} />
                        )}
                        <h3 className="font-bold text-base text-[#14283D] leading-snug">
                          {journal.title}
                        </h3>
                        <p className="text-xs text-slate-400 font-normal">
                          {journal.publisher}
                        </p>
                      </div>

                      <button
                        onClick={() => toggleCompareJournal(journal.id)}
                        title="Remove from comparison"
                        className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-200/60 transition-colors"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>

            {/* Matrix Rows */}
            <tbody className="divide-y divide-slate-100 text-xs">
              {/* Row 1: Aims & Scope */}
              <tr className="hover:bg-slate-50/50 transition-colors">
                <td className="p-5 font-semibold text-slate-500">Aims & scope</td>
                {comparedJournals.map((j) => (
                  <td
                    key={j.id}
                    className={`p-5 leading-relaxed border-l border-slate-100 ${
                      j.id === 'jrn_01'
                        ? 'font-medium text-[#0F766E]'
                        : 'text-slate-600'
                    }`}
                  >
                    {j.aimsAndScope}
                  </td>
                ))}
              </tr>

              {/* Row 2: Subject Category */}
              <tr className="hover:bg-slate-50/50 transition-colors">
                <td className="p-5 font-semibold text-slate-500">Subject category</td>
                {comparedJournals.map((j) => (
                  <td key={j.id} className="p-5 text-slate-700 border-l border-slate-100">
                    {j.subjectCategory}
                  </td>
                ))}
              </tr>

              {/* Row 3: Scope Match */}
              <tr className="hover:bg-slate-50/50 transition-colors">
                <td className="p-5 font-semibold text-slate-500">Scope match</td>
                {comparedJournals.map((j) => {
                  const isTop = j.matchScore === Math.max(...comparedJournals.map((x) => x.matchScore || 0));
                  return (
                    <td key={j.id} className="p-5 border-l border-slate-100">
                      <div className="flex items-center justify-between">
                        <span className={`text-sm ${isTop ? 'font-bold text-[#0F766E]' : 'font-medium text-slate-700'}`}>
                          {j.matchScore}%
                        </span>
                        {isTop && <Check className="w-4 h-4 text-[#0F766E]" />}
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Row 4: Quartile */}
              <tr className="hover:bg-slate-50/50 transition-colors">
                <td className="p-5 font-semibold text-slate-500">Quartile</td>
                {comparedJournals.map((j) => {
                  const isTop = j.quartile === 'Q1';
                  return (
                    <td key={j.id} className="p-5 border-l border-slate-100">
                      <div className="flex items-center justify-between">
                        <span className={`font-semibold ${isTop ? 'text-[#0F766E]' : 'text-slate-700'}`}>
                          {j.quartile}
                        </span>
                        {isTop && <Check className="w-4 h-4 text-[#0F766E]" />}
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Row 5: CiteScore */}
              <tr className="hover:bg-slate-50/50 transition-colors">
                <td className="p-5 font-semibold text-slate-500">CiteScore</td>
                {comparedJournals.map((j) => {
                  const isTop = j.citeScore === Math.max(...comparedJournals.map((x) => x.citeScore));
                  return (
                    <td key={j.id} className="p-5 border-l border-slate-100">
                      <div className="flex items-center justify-between">
                        <span className={`text-sm ${isTop ? 'font-bold text-[#0F766E]' : 'font-medium text-slate-700'}`}>
                          {j.citeScore}
                        </span>
                        {isTop && <Check className="w-4 h-4 text-[#0F766E]" />}
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Row 6: Impact Factor */}
              <tr className="hover:bg-slate-50/50 transition-colors">
                <td className="p-5 font-semibold text-slate-500">Impact factor</td>
                {comparedJournals.map((j) => {
                  const isTop = j.impactFactor === Math.max(...comparedJournals.map((x) => x.impactFactor));
                  return (
                    <td key={j.id} className="p-5 border-l border-slate-100">
                      <div className="flex items-center justify-between">
                        <span className={`text-sm ${isTop ? 'font-bold text-[#0F766E]' : 'font-medium text-slate-700'}`}>
                          {j.impactFactor}
                        </span>
                        {isTop && <Check className="w-4 h-4 text-[#0F766E]" />}
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Row 7: Open Access */}
              <tr className="hover:bg-slate-50/50 transition-colors">
                <td className="p-5 font-semibold text-slate-500">Open access</td>
                {comparedJournals.map((j) => {
                  const isOA = j.openAccessType === 'Open access';
                  return (
                    <td key={j.id} className="p-5 border-l border-slate-100">
                      <div className="flex items-center justify-between">
                        <span className={`font-semibold ${isOA ? 'text-[#0F766E]' : 'text-slate-600'}`}>
                          {j.openAccessType}
                        </span>
                        {isOA && <Check className="w-4 h-4 text-[#0F766E]" />}
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Row 8: Review Time */}
              <tr className="hover:bg-slate-50/50 transition-colors">
                <td className="p-5 font-semibold text-slate-500">Review time</td>
                {comparedJournals.map((j) => {
                  const isFastest = j.reviewWeeks === Math.min(...comparedJournals.map((x) => x.reviewWeeks));
                  return (
                    <td key={j.id} className="p-5 border-l border-slate-100">
                      <div className="flex items-center justify-between">
                        <span className={`font-semibold ${isFastest ? 'text-[#0F766E]' : 'text-slate-700'}`}>
                          {j.reviewWeeks} weeks
                        </span>
                        {isFastest && <Check className="w-4 h-4 text-[#0F766E]" />}
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Row 9: Acceptance Rate */}
              <tr className="hover:bg-slate-50/50 transition-colors">
                <td className="p-5 font-semibold text-slate-500">Acceptance rate</td>
                {comparedJournals.map((j) => {
                  const isHighest = j.acceptanceRate === Math.max(...comparedJournals.map((x) => x.acceptanceRate));
                  return (
                    <td key={j.id} className="p-5 border-l border-slate-100">
                      <div className="flex items-center justify-between">
                        <span className={`font-semibold ${isHighest ? 'text-[#0F766E]' : 'text-slate-700'}`}>
                          {j.acceptanceRate}%
                        </span>
                        {isHighest && <Check className="w-4 h-4 text-[#0F766E]" />}
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Bottom Action Row */}
              <tr className="bg-slate-50/40">
                <td className="p-5"></td>
                {comparedJournals.map((j) => {
                  const isChosen = selectedTargetId === j.id;
                  return (
                    <td key={j.id} className="p-5 border-l border-slate-100">
                      <Button
                        size="sm"
                        variant={isChosen ? 'primary' : 'secondary'}
                        onClick={() => handleSelectJournal(j.id, j.title)}
                        leftIcon={
                          isChosen ? (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          ) : (
                            <Bookmark className="w-3.5 h-3.5 text-[#0F766E]" />
                          )
                        }
                        className="w-full shadow-2xs"
                      >
                        {isChosen ? 'Target Journal' : 'Select journal'}
                      </Button>
                    </td>
                  );
                })}
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Footnote Banner */}
      <div className="p-3.5 bg-[#F0FDF4] border border-[#DCFCE7] rounded-2xl flex items-center gap-2.5 text-xs text-[#166534]">
        <Info className="w-4 h-4 shrink-0 text-[#16A34A]" />
        <span>
          Mint highlights the strongest value in each row. Journal profiles and metrics are illustrative, not a verified dataset.
        </span>
      </div>

      {/* Add Journal Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h3 className="text-lg font-bold text-[#14283D] mb-1">Add to Comparison</h3>
            <p className="text-xs text-slate-500 mb-4">Choose from available catalog journals to compare side by side.</p>

            <div className="space-y-2 max-h-60 overflow-y-auto">
              {journals.map((j) => {
                const isSelected = selectedCompareJournalIds.includes(j.id);
                return (
                  <div
                    key={j.id}
                    onClick={() => toggleCompareJournal(j.id)}
                    className={`p-3 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                      isSelected
                        ? 'border-[#0F766E] bg-[#CCFBF1]/20 font-semibold'
                        : 'border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <div>
                      <p className="text-xs text-slate-800">{j.title}</p>
                      <p className="text-[11px] text-slate-400">{j.publisher} · {j.quartile}</p>
                    </div>
                    {isSelected ? (
                      <Check className="w-4 h-4 text-[#0F766E]" />
                    ) : (
                      <Plus className="w-4 h-4 text-slate-400" />
                    )}
                  </div>
                );
              })}
            </div>

            <div className="flex justify-end pt-4 mt-3 border-t border-slate-100">
              <Button onClick={() => setIsAddModalOpen(false)}>Done</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
