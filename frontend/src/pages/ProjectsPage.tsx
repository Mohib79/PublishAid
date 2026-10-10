import React, { useState } from 'react';
import { Plus, Search, FolderKanban, FileText, ArrowRight, CheckCircle2, Bookmark, ExternalLink } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { useNavigate } from 'react-router-dom';

export const ProjectsPage: React.FC = () => {
  const { projects, activeProjectId, setActiveProjectId, addProject } = useApp();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [filterField, setFilterField] = useState('All');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newField, setNewField] = useState('Environmental science');
  const [newAbstract, setNewAbstract] = useState('');

  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.field.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesField = filterField === 'All' || p.field === filterField;
    return matchesSearch && matchesField;
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    const created = addProject(newTitle.trim(), newField, newAbstract);
    setActiveProjectId(created.id);
    setIsModalOpen(false);
    setNewTitle('');
    setNewAbstract('');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
            Manuscript Workspaces
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage your draft papers, target venues, and ongoing compliance reports.
          </p>
        </div>

        <Button
          onClick={() => setIsModalOpen(true)}
          leftIcon={<Plus className="w-4 h-4 stroke-[2.5]" />}
        >
          New Project
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-2xs flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search projects by title or field..."
            className="w-full pl-10 pr-4 h-[40px] rounded-xl border border-slate-200 text-sm focus:border-[#0F766E] focus:ring-1 focus:ring-[#0F766E] outline-none"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs font-semibold text-slate-500 shrink-0">Field:</span>
          <select
            value={filterField}
            onChange={(e) => setFilterField(e.target.value)}
            className="h-[40px] px-3 rounded-xl border border-slate-200 text-sm bg-white text-slate-700 outline-none focus:border-[#0F766E] cursor-pointer"
          >
            <option value="All">All Disciplines</option>
            <option value="Environmental science">Environmental science</option>
            <option value="Urban studies">Urban studies</option>
            <option value="Ecology">Ecology</option>
            <option value="Energy systems">Energy systems</option>
          </select>
        </div>
      </div>

      {/* Projects Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredProjects.map((project) => {
          const isActive = project.id === activeProjectId;
          return (
            <div
              key={project.id}
              className={`bg-white rounded-2xl p-5 border transition-all ${
                isActive
                  ? 'border-[#0F766E] ring-2 ring-[#0F766E]/15 shadow-sm'
                  : 'border-slate-200/80 hover:border-slate-300 shadow-2xs'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                      isActive ? 'bg-[#0F766E] text-white' : 'bg-[#CCFBF1] text-[#0F766E]'
                    }`}
                  >
                    <FolderKanban className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-slate-500">{project.field}</span>
                    <span className="text-slate-300 mx-1.5">·</span>
                    <span className="text-xs text-slate-400">{project.updatedAt}</span>
                  </div>
                </div>

                <StatusBadge status={project.status} />
              </div>

              <h3 className="font-bold text-base text-[#14283D] mt-3.5 leading-snug">
                {project.title}
              </h3>

              <p className="text-xs text-slate-500 line-clamp-2 mt-2 leading-relaxed">
                {project.abstract || 'No abstract text attached yet. Add abstract to run journal matching.'}
              </p>

              {/* Target Journal / File Meta */}
              <div className="mt-4 pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between text-xs text-slate-600 gap-2">
                <div className="flex items-center gap-1.5">
                  <Bookmark className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-slate-500">Target:</span>
                  <span className="font-medium text-slate-700">
                    {project.targetJournalTitle || 'None selected'}
                  </span>
                </div>

                {project.fileName && (
                  <div className="flex items-center gap-1.5 text-slate-500">
                    <FileText className="w-3.5 h-3.5 text-slate-400" />
                    <span>{project.fileName}</span>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="mt-4 pt-3 flex items-center justify-between gap-2">
                {isActive ? (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#0F766E]">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Active Workspace
                  </span>
                ) : (
                  <button
                    onClick={() => setActiveProjectId(project.id)}
                    className="text-xs font-semibold text-slate-600 hover:text-[#0F766E] transition-colors cursor-pointer"
                  >
                    Set as Active
                  </button>
                )}

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setActiveProjectId(project.id);
                      navigate('/compliance');
                    }}
                  >
                    Audit
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => {
                      setActiveProjectId(project.id);
                      navigate('/finder');
                    }}
                    rightIcon={<ArrowRight className="w-3 h-3" />}
                  >
                    Open
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <h3 className="text-lg font-bold text-[#14283D] mb-1">New Manuscript Workspace</h3>
            <p className="text-xs text-slate-500 mb-4">Set up a workspace for your paper draft.</p>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Title *
                </label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Distributed photovoltaic grid performance..."
                  className="w-full px-3.5 h-[40px] rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Field
                </label>
                <select
                  value={newField}
                  onChange={(e) => setNewField(e.target.value)}
                  className="w-full px-3.5 h-[40px] rounded-xl border border-slate-300 text-sm bg-white focus:border-[#0F766E] outline-none cursor-pointer"
                >
                  <option value="Environmental science">Environmental science</option>
                  <option value="Urban studies">Urban studies</option>
                  <option value="Computer science">Computer science</option>
                  <option value="Ecology">Ecology</option>
                  <option value="Energy systems">Energy systems</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Abstract
                </label>
                <textarea
                  rows={3}
                  value={newAbstract}
                  onChange={(e) => setNewAbstract(e.target.value)}
                  placeholder="Paste abstract draft..."
                  className="w-full p-3 rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit">Create</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
