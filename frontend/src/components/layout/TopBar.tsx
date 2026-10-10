import React from 'react';
import { HelpCircle, Settings, ChevronRight } from 'lucide-react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { PublishAidLogo } from '../common/PublishAidLogo';

export const TopBar: React.FC = () => {
  const { user } = useApp();
  const location = useLocation();
  const navigate = useNavigate();

  const getPageTitle = () => {
    const path = location.pathname;
    if (path === '/' || path === '/dashboard') return 'Dashboard';
    if (path.startsWith('/projects')) return 'Projects';
    if (path.startsWith('/finder')) return 'Journal Finder';
    if (path.startsWith('/compare')) return 'Compare Journals';
    if (path.startsWith('/guidelines')) return 'Guidelines & Templates';
    if (path.startsWith('/transformation')) return 'Manuscript Transformation';
    if (path.startsWith('/converter')) return 'Document Converter';
    if (path.startsWith('/summarizer')) return 'Paper Summarizer';
    if (path.startsWith('/compliance')) return 'Compliance Check';
    if (path.startsWith('/settings')) return 'Settings';
    return 'Workspace';
  };

  return (
    <header className="h-[72px] bg-white border-b border-slate-200/80 px-6 sm:px-8 flex items-center justify-between sticky top-0 z-20">
      {/* Left Breadcrumb */}
      <div className="flex items-center gap-3 text-sm font-medium text-slate-500">
        <Link to="/dashboard" className="flex items-center gap-2 text-slate-700 hover:text-[#0F766E] transition-colors">
          <PublishAidLogo variant="icon-only" iconSize={20} />
          <span className="font-semibold text-slate-800">PublishAid</span>
        </Link>
        <span className="text-slate-300">/</span>
        <span className="text-slate-600 font-medium">{getPageTitle()}</span>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        <button
          title="Help & Documentation"
          onClick={() => window.open('https://github.com', '_blank')}
          className="w-9 h-9 rounded-full flex items-center justify-center text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <HelpCircle className="w-5 h-5 stroke-[1.75]" />
        </button>

        <button
          title="Settings"
          onClick={() => navigate('/settings')}
          className="w-9 h-9 rounded-full flex items-center justify-center text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <Settings className="w-5 h-5 stroke-[1.75]" />
        </button>

        {user && (
          <button
            onClick={() => navigate('/settings')}
            title={`${user.fullName} (${user.plan})`}
            className="w-9 h-9 rounded-full bg-[#CCFBF1] text-[#0F766E] font-semibold text-xs flex items-center justify-center border border-[#99F6E4] shadow-2xs hover:scale-105 transition-transform cursor-pointer ml-1"
          >
            {user.avatarInitials}
          </button>
        )}
      </div>
    </header>
  );
};
