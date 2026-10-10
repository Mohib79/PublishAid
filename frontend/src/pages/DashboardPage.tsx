import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Folder,
  Bookmark,
  RefreshCw,
  ShieldCheck,
  Plus,
  Search,
  ArrowUpRight,
  FolderPlus,
  ArrowRight,
  X,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, projects, conversions, complianceReport, activities, addProject } = useApp();

  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newField, setNewField] = useState('Environmental science');
  const [newAbstract, setNewAbstract] = useState('');

  const handleCreateProject = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    addProject(newTitle.trim(), newField, newAbstract);
    setNewTitle('');
    setNewAbstract('');
    setIsNewProjectModalOpen(false);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Welcome Row */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
            Welcome back, {user ? user.fullName.split(' ')[1] || user.fullName : 'Researcher'}.
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            A little less admin. A little more research. Here's where your work stands.
          </p>
        </div>

        <Button
          onClick={() => setIsNewProjectModalOpen(true)}
          leftIcon={<Plus className="w-4 h-4 stroke-[2.5]" />}
          className="shadow-sm"
        >
          New Project
        </Button>
      </div>

      {/* 4 KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Active Projects */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium text-slate-500">Active Projects</span>
            <Folder className="w-5 h-5 text-slate-400 stroke-[1.75]" />
          </div>
          <div className="text-3xl font-extrabold text-[#14283D] mt-2">
            {projects.length * 2}
          </div>
          <p className="text-xs text-slate-400 mt-2">
            3 moving toward submission
          </p>
        </div>

        {/* Card 2: Shortlisted Journals */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium text-slate-500">Shortlisted Journals</span>
            <Bookmark className="w-5 h-5 text-slate-400 stroke-[1.75]" />
          </div>
          <div className="text-3xl font-extrabold text-[#14283D] mt-2">
            12
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Across 4 research projects
          </p>
        </div>

        {/* Card 3: Conversions */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium text-slate-500">Conversions</span>
            <RefreshCw className="w-5 h-5 text-slate-400 stroke-[1.75]" />
          </div>
          <div className="text-3xl font-extrabold text-[#14283D] mt-2">
            {conversions.length * 8}
          </div>
          <p className="text-xs text-slate-400 mt-2">
            6 completed this month
          </p>
        </div>

        {/* Card 4: Compliance Reports */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium text-slate-500">Compliance Reports</span>
            <ShieldCheck className="w-5 h-5 text-slate-400 stroke-[1.75]" />
          </div>
          <div className="text-3xl font-extrabold text-[#14283D] mt-2">
            16
          </div>
          <p className="text-xs text-slate-400 mt-2">
            4 ready for submission
          </p>
        </div>
      </div>

      {/* Quick Actions Card */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-[#14283D]">
            Keep your research moving
          </h2>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            QUICK ACTIONS
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {/* Action 1: New Project */}
          <button
            onClick={() => setIsNewProjectModalOpen(true)}
            className="group flex flex-col justify-between p-4 bg-slate-50/80 hover:bg-[#CCFBF1]/40 border border-slate-200/80 hover:border-[#99F6E4] rounded-xl text-left transition-all cursor-pointer"
          >
            <div className="flex items-center justify-between w-full">
              <span className="flex items-center gap-2 font-semibold text-sm text-[#14283D] group-hover:text-[#0F766E]">
                <Plus className="w-4 h-4 text-[#0F766E]" />
                New Project
              </span>
              <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-[#0F766E] transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </div>
            <p className="text-xs text-slate-500 mt-3">Start a research workspace</p>
          </button>

          {/* Action 2: Find Journals */}
          <Link
            to="/finder"
            className="group flex flex-col justify-between p-4 bg-slate-50/80 hover:bg-[#CCFBF1]/40 border border-slate-200/80 hover:border-[#99F6E4] rounded-xl text-left transition-all cursor-pointer"
          >
            <div className="flex items-center justify-between w-full">
              <span className="flex items-center gap-2 font-semibold text-sm text-[#14283D] group-hover:text-[#0F766E]">
                <Search className="w-4 h-4 text-[#0F766E]" />
                Find Journals
              </span>
              <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-[#0F766E] transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </div>
            <p className="text-xs text-slate-500 mt-3">Discover your best match</p>
          </Link>

          {/* Action 3: Convert Document */}
          <Link
            to="/converter"
            className="group flex flex-col justify-between p-4 bg-slate-50/80 hover:bg-[#CCFBF1]/40 border border-slate-200/80 hover:border-[#99F6E4] rounded-xl text-left transition-all cursor-pointer"
          >
            <div className="flex items-center justify-between w-full">
              <span className="flex items-center gap-2 font-semibold text-sm text-[#14283D] group-hover:text-[#0F766E]">
                <RefreshCw className="w-4 h-4 text-[#0F766E]" />
                Convert Document
              </span>
              <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-[#0F766E] transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </div>
            <p className="text-xs text-slate-500 mt-3">Word ↔ LaTeX, simplified</p>
          </Link>

          {/* Action 4: Check Compliance */}
          <Link
            to="/compliance"
            className="group flex flex-col justify-between p-4 bg-slate-50/80 hover:bg-[#CCFBF1]/40 border border-slate-200/80 hover:border-[#99F6E4] rounded-xl text-left transition-all cursor-pointer"
          >
            <div className="flex items-center justify-between w-full">
              <span className="flex items-center gap-2 font-semibold text-sm text-[#14283D] group-hover:text-[#0F766E]">
                <ShieldCheck className="w-4 h-4 text-[#0F766E]" />
                Check Compliance
              </span>
              <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-[#0F766E] transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </div>
            <p className="text-xs text-slate-500 mt-3">Submit with confidence</p>
          </Link>
        </div>
      </div>

      {/* Two-Column Section: Recent Projects & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Recent Projects (2/3 width) */}
        <div className="lg:col-span-2 bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-[#14283D]">
              Recent Projects
            </h2>
            <Link
              to="/projects"
              className="text-xs font-semibold text-slate-500 hover:text-[#0F766E] flex items-center gap-1 transition-colors"
            >
              <span>View all</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-100 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  <th className="pb-3 font-semibold">PROJECT</th>
                  <th className="pb-3 font-semibold">TARGET JOURNAL</th>
                  <th className="pb-3 font-semibold text-right">STATUS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {projects.map((proj) => (
                  <tr
                    key={proj.id}
                    onClick={() => navigate(`/projects`)}
                    className="group hover:bg-slate-50/70 cursor-pointer transition-colors"
                  >
                    <td className="py-3.5 pr-4">
                      <div className="font-semibold text-slate-800 group-hover:text-[#0F766E] transition-colors leading-snug">
                        {proj.title}
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        {proj.field} · {proj.updatedAt}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-xs font-medium text-slate-600">
                      {proj.targetJournalTitle || 'Not selected'}
                    </td>
                    <td className="py-3.5 pl-4 text-right">
                      <StatusBadge status={proj.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Recent Activity (1/3 width) */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs">
          <h2 className="text-base font-bold text-[#14283D] mb-4">
            Recent Activity
          </h2>

          <div className="space-y-4">
            {activities.map((act) => {
              const getIcon = () => {
                switch (act.type) {
                  case 'compliance':
                    return <ShieldCheck className="w-4 h-4 text-[#0F766E]" />;
                  case 'journal':
                    return <Bookmark className="w-4 h-4 text-[#0F766E]" />;
                  case 'conversion':
                    return <RefreshCw className="w-4 h-4 text-[#0F766E]" />;
                  case 'project':
                    return <FolderPlus className="w-4 h-4 text-[#0F766E]" />;
                  default:
                    return <Folder className="w-4 h-4 text-[#0F766E]" />;
                }
              };

              return (
                <div key={act.id} className="flex items-start gap-3 group">
                  <div className="w-8 h-8 rounded-lg bg-[#CCFBF1] flex items-center justify-center shrink-0 border border-[#99F6E4]/50 mt-0.5">
                    {getIcon()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-slate-800 leading-tight">
                      {act.title}
                    </p>
                    <p className="text-[11px] text-slate-500 truncate mt-0.5">
                      {act.subtitle}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {act.timestamp}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Modal: Create New Project */}
      {isNewProjectModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 relative">
            <button
              onClick={() => setIsNewProjectModalOpen(false)}
              className="absolute right-4 top-4 text-slate-400 hover:text-slate-600 p-1"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-[#CCFBF1] text-[#0F766E] flex items-center justify-center">
                <FolderPlus className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-[#14283D]">Create Manuscript Workspace</h3>
                <p className="text-xs text-slate-500">Organize drafts, candidate journals, and compliance records.</p>
              </div>
            </div>

            <form onSubmit={handleCreateProject} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Project Title *
                </label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Urban microclimate resilience and tree canopy effects"
                  className="w-full px-3.5 h-[40px] rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Primary Research Field
                </label>
                <select
                  value={newField}
                  onChange={(e) => setNewField(e.target.value)}
                  className="w-full px-3.5 h-[40px] rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 outline-none bg-white cursor-pointer"
                >
                  <option value="Environmental science">Environmental science</option>
                  <option value="Urban studies">Urban studies</option>
                  <option value="Computer science">Computer science</option>
                  <option value="Ecology">Ecology</option>
                  <option value="Energy systems">Energy systems</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Initial Abstract / Description (Optional)
                </label>
                <textarea
                  rows={3}
                  value={newAbstract}
                  onChange={(e) => setNewAbstract(e.target.value)}
                  placeholder="Paste abstract draft or research statement..."
                  className="w-full p-3 rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setIsNewProjectModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit">
                  Create Workspace
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
