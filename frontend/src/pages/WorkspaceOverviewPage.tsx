import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  FolderKanban,
  ArrowLeft,
  Bookmark,
  Calendar,
  Clock,
  FileText,
  UploadCloud,
  CheckCircle2,
  Trash2,
  Edit3,
  ExternalLink,
  Loader2,
  AlertCircle,
  Tag,
  Check,
  X,
  History,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { getProjectById, updateProject, deleteProject, getProjectActivity } from '../lib/api';
import { Project, ProjectActivityEvent } from '../types';

export const WorkspaceOverviewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { activeProjectId, setActiveProjectId, refreshProjects } = useApp();

  const [project, setProject] = useState<Project | null>(null);
  const [activities, setActivities] = useState<ProjectActivityEvent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Edit State
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editTitle, setEditTitle] = useState<string>('');
  const [editField, setEditField] = useState<string>('');
  const [editAbstract, setEditAbstract] = useState<string>('');
  const [editKeywords, setEditKeywords] = useState<string>('');
  const [editStatus, setEditStatus] = useState<string>('draft');
  const [isSaving, setIsSaving] = useState<boolean>(false);

  // Delete State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const fetchProjectDetails = async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getProjectById(id);
      setProject(data);
      setEditTitle(data.title);
      setEditField(data.researchField || data.field || '');
      setEditAbstract(data.abstract || '');
      setEditKeywords(data.keywords ? data.keywords.join(', ') : '');
      setEditStatus(data.status || 'draft');

      if (data.recentActivity) {
        setActivities(data.recentActivity);
      } else {
        const actData = await getProjectActivity(id);
        setActivities(actData);
      }
    } catch (err: any) {
      setError(err.message || 'Project not found');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProjectDetails();
  }, [id]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !project || !editTitle.trim()) return;
    setIsSaving(true);
    try {
      const kwList = editKeywords
        .split(',')
        .map(k => k.trim())
        .filter(Boolean);

      const updated = await updateProject(id, {
        title: editTitle.trim(),
        researchField: editField.trim() || undefined,
        field: editField.trim() || undefined,
        abstract: editAbstract.trim() || null,
        keywords: kwList,
        status: editStatus,
      });

      setProject(prev => (prev ? { ...prev, ...updated } : updated));
      setIsEditing(false);
      refreshProjects();

      // Refresh activity feed
      const actData = await getProjectActivity(id);
      setActivities(actData);
    } catch (err: any) {
      alert(err.message || 'Failed to update project');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!id) return;
    setIsDeleting(true);
    try {
      await deleteProject(id);
      await refreshProjects();
      navigate('/projects');
    } catch (err: any) {
      alert(err.message || 'Failed to delete workspace');
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-500 space-y-3">
        <Loader2 className="w-8 h-8 text-[#0F766E] animate-spin" />
        <p className="text-sm font-medium">Opening manuscript workspace...</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="bg-white rounded-2xl p-10 border border-slate-200/80 shadow-2xs text-center max-w-lg mx-auto my-12 space-y-4">
        <div className="w-12 h-12 rounded-full bg-red-50 text-red-600 flex items-center justify-center mx-auto">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-bold text-slate-900">Project Not Found</h2>
        <p className="text-xs text-slate-500 leading-relaxed">
          {error || "The manuscript workspace you requested could not be found or you don't have permission to access it."}
        </p>
        <Button onClick={() => navigate('/projects')} leftIcon={<ArrowLeft className="w-4 h-4" />}>
          Back to Workspaces
        </Button>
      </div>
    );
  }

  const isActive = project.id === activeProjectId;
  const targetJournalTitle = project.targetJournal?.title || project.targetJournalTitle || 'No target journal selected';

  return (
    <div className="space-y-6">
      {/* Top Navigation Row */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/projects')}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-[#0F766E] transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>All Workspaces</span>
        </button>

        <div className="flex items-center gap-2">
          {!isActive && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setActiveProjectId(project.id)}
            >
              Set as Active Workspace
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsEditing(!isEditing)}
            leftIcon={<Edit3 className="w-3.5 h-3.5" />}
          >
            {isEditing ? 'Cancel Edit' : 'Edit Details'}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsDeleteModalOpen(true)}
            className="text-red-600 hover:text-red-700 hover:bg-red-50"
            leftIcon={<Trash2 className="w-3.5 h-3.5" />}
          >
            Delete
          </Button>
        </div>
      </div>

      {/* Main Workspace Header Card */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div className="flex items-start gap-3">
            <div
              className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 ${
                isActive ? 'bg-[#0F766E] text-white shadow-xs' : 'bg-[#CCFBF1] text-[#0F766E]'
              }`}
            >
              <FolderKanban className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  {project.researchField || project.field || 'General Field'}
                </span>
                <span className="text-slate-300">·</span>
                <span className="text-xs text-slate-400">Workspace #{project.id}</span>
                {isActive && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold text-[#0F766E] bg-[#CCFBF1]/50 px-2 py-0.5 rounded-full border border-[#99F6E4]">
                    <CheckCircle2 className="w-3 h-3" />
                    Active Workspace
                  </span>
                )}
              </div>
              <h1 className="text-xl sm:text-2xl font-extrabold text-[#14283D] mt-1 leading-snug">
                {project.title}
              </h1>
            </div>
          </div>

          <StatusBadge status={project.status || 'Draft'} />
        </div>

        {/* Edit Form */}
        {isEditing ? (
          <form onSubmit={handleSave} className="p-4 bg-slate-50/80 rounded-xl border border-slate-200/80 space-y-3 mt-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">Update Project Details</h4>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Title *</label>
              <input
                type="text"
                required
                value={editTitle}
                onChange={e => setEditTitle(e.target.value)}
                className="w-full px-3 h-[38px] rounded-lg border border-slate-300 text-sm focus:border-[#0F766E] outline-none"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Research Field</label>
                <input
                  type="text"
                  value={editField}
                  onChange={e => setEditField(e.target.value)}
                  placeholder="e.g. Computer Science"
                  className="w-full px-3 h-[38px] rounded-lg border border-slate-300 text-sm focus:border-[#0F766E] outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Status</label>
                <select
                  value={editStatus}
                  onChange={e => setEditStatus(e.target.value)}
                  className="w-full px-3 h-[38px] rounded-lg border border-slate-300 text-sm bg-white focus:border-[#0F766E] outline-none cursor-pointer"
                >
                  <option value="draft">Draft</option>
                  <option value="in_progress">In Progress</option>
                  <option value="ready_to_submit">Ready to Submit</option>
                  <option value="submitted">Submitted</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Abstract</label>
              <textarea
                rows={4}
                value={editAbstract}
                onChange={e => setEditAbstract(e.target.value)}
                placeholder="Paste abstract draft..."
                className="w-full p-3 rounded-lg border border-slate-300 text-sm focus:border-[#0F766E] outline-none resize-none leading-relaxed"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Keywords (comma-separated)</label>
              <input
                type="text"
                value={editKeywords}
                onChange={e => setEditKeywords(e.target.value)}
                placeholder="e.g. federated learning, computer vision, optimization"
                className="w-full px-3 h-[38px] rounded-lg border border-slate-300 text-sm focus:border-[#0F766E] outline-none"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="secondary" size="sm" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" isLoading={isSaving}>
                Save Changes
              </Button>
            </div>
          </form>
        ) : (
          <>
            <p className="text-sm text-slate-600 leading-relaxed pt-1">
              {project.abstract || (
                <span className="italic text-slate-400">
                  No manuscript abstract added yet. Click &quot;Edit Details&quot; to attach an abstract for semantic journal matching.
                </span>
              )}
            </p>

            {/* Keyword tags */}
            {project.keywords && project.keywords.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap pt-2">
                <Tag className="w-3.5 h-3.5 text-slate-400 mr-1" />
                {project.keywords.map((kw, i) => (
                  <span
                    key={i}
                    className="inline-block px-2.5 py-0.5 bg-slate-100 text-slate-600 text-xs font-medium rounded-full border border-slate-200"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Two-Column Section: Overview Cards on Left, Audit History on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left Column (2 Cols) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Target Journal & Shortlist Card */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Bookmark className="w-4 h-4 text-[#0F766E]" />
                <h3 className="text-sm font-bold text-[#14283D]">Target Journal & Candidate Venues</h3>
              </div>
              <Link
                to="/finder"
                className="text-xs font-semibold text-[#0F766E] hover:underline flex items-center gap-1"
              >
                <span>Find Journals</span>
                <ExternalLink className="w-3 h-3" />
              </Link>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-100 space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Target Venue</span>
                <p className="text-sm font-bold text-[#14283D] leading-snug">
                  {targetJournalTitle}
                </p>
                <p className="text-xs text-slate-500">
                  {project.targetJournal?.publisher ? `Publisher: ${project.targetJournal.publisher}` : 'Selection used for compliance & conversion'}
                </p>
              </div>

              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-100 space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Shortlisted Venues</span>
                <p className="text-2xl font-extrabold text-[#14283D]">
                  {project.shortlistedCount ?? 0}
                </p>
                <Link
                  to="/compare"
                  className="text-xs font-semibold text-[#0F766E] hover:underline inline-block pt-0.5"
                >
                  View in Comparison Matrix &rarr;
                </Link>
              </div>
            </div>
          </div>

          {/* Manuscript Attachment Card */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-[#0F766E]" />
                <h3 className="text-sm font-bold text-[#14283D]">Draft Manuscript File</h3>
              </div>
              <span className="text-[11px] font-semibold text-slate-400">
                Temporary Session Storage
              </span>
            </div>

            {project.manuscript && project.manuscript.available ? (
              <div className="p-4 bg-teal-50/40 rounded-xl border border-teal-200/60 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-[#0F766E] text-white flex items-center justify-center shrink-0">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-[#14283D]">{project.manuscript.fileName}</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {(project.manuscript.sizeBytes / (1024 * 1024)).toFixed(2)} MB · Auto-deletes in 2 hours
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="secondary" onClick={() => navigate('/compliance')}>
                    Check Compliance
                  </Button>
                </div>
              </div>
            ) : (
              <div className="border-2 border-dashed border-slate-200 hover:border-[#0F766E]/50 rounded-2xl p-6 flex flex-col items-center justify-center bg-slate-50/50 text-center space-y-2">
                <UploadCloud className="w-8 h-8 text-[#0F766E] stroke-[1.5]" />
                <p className="text-sm font-bold text-[#14283D]">Attach manuscript draft</p>
                <p className="text-xs text-slate-400 max-w-sm">
                  Upload .docx, .tex or .pdf up to 20 MB. Draft files are stored securely in temporary execution storage and deleted automatically post-session.
                </p>
                <div className="pt-2">
                  <Button size="sm" variant="secondary" onClick={() => navigate('/finder')}>
                    Attach in Journal Finder
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Activity History (1 Col) */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-2xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-[#0F766E]" />
              <h3 className="text-sm font-bold text-[#14283D]">Workspace Activity</h3>
            </div>
            <span className="text-xs text-slate-400 font-semibold">{activities.length} Events</span>
          </div>

          <div className="space-y-3.5">
            {activities.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-6">No activity recorded yet.</p>
            ) : (
              activities.map(act => {
                const formatEventLabel = (type: string) => {
                  switch (type) {
                    case 'project_created':
                      return 'Project Created';
                    case 'project_updated':
                      return 'Details Updated';
                    case 'project_status_changed':
                      return `Status Changed to ${act.details.to || ''}`;
                    case 'journal_shortlisted':
                      return `Shortlisted: ${act.journalTitle || 'Journal'}`;
                    case 'journal_unshortlisted':
                      return `Unshortlisted: ${act.journalTitle || 'Journal'}`;
                    case 'target_journal_set':
                      return `Target Set: ${act.journalTitle || 'Journal'}`;
                    case 'target_journal_cleared':
                      return 'Target Venue Cleared';
                    case 'manuscript_uploaded':
                      return 'Manuscript Uploaded';
                    case 'manuscript_removed':
                      return 'Manuscript Removed';
                    case 'manuscript_purged':
                      return 'Manuscript Purged (TTL)';
                    default:
                      return type.replace(/_/g, ' ');
                  }
                };

                return (
                  <div key={act.id} className="flex items-start gap-2.5 text-xs">
                    <div className="w-2 h-2 rounded-full bg-[#0F766E] mt-1.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-slate-800 leading-snug">
                        {formatEventLabel(act.eventType)}
                      </p>
                      <p className="text-[10px] text-slate-400 mt-0.5">
                        {new Date(act.createdAt).toLocaleString()}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <h3 className="text-base font-bold text-red-600">Delete Manuscript Workspace?</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to delete <strong className="text-slate-800">&quot;{project.title}&quot;</strong>? This action will permanently remove the workspace, its shortlist records, and any attached draft file.
            </p>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                className="bg-red-600 hover:bg-red-700 text-white"
                onClick={handleDelete}
                isLoading={isDeleting}
              >
                Confirm Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

