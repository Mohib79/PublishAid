import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FolderKanban,
  Search,
  BookOpen,
  FileSpreadsheet,
  FileEdit,
  ArrowLeftRight,
  FileText,
  ShieldCheck,
  Settings as SettingsIcon,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { PublishAidLogo } from '../common/PublishAidLogo';

export const Sidebar: React.FC = () => {
  const { isSidebarCollapsed, toggleSidebar, user } = useApp();

  const navItems = [
    { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { label: 'Projects', path: '/projects', icon: FolderKanban },
    { label: 'Journal Finder', path: '/finder', icon: Search },
    { label: 'Compare Journals', path: '/compare', icon: BookOpen },
    { label: 'Guidelines & Templates', path: '/guidelines', icon: FileSpreadsheet },
    { label: 'Manuscript Transformation', path: '/transformation', icon: FileEdit },
    { label: 'Document Converter', path: '/converter', icon: ArrowLeftRight },
    { label: 'Paper Summarizer', path: '/summarizer', icon: FileText },
    { label: 'Compliance Check', path: '/compliance', icon: ShieldCheck },
  ];

  return (
    <aside
      className={`bg-white border-r border-slate-200/90 h-screen sticky top-0 flex flex-col justify-between transition-all duration-300 z-30 shrink-0 ${
        isSidebarCollapsed ? 'w-[78px]' : 'w-[260px]'
      }`}
    >
      {/* Top Header & Brand */}
      <div className="flex flex-col">
        <div className="h-[72px] px-5 flex items-center justify-between border-b border-slate-100">
          <NavLink to="/dashboard" className="flex items-center gap-2 overflow-hidden">
            <PublishAidLogo
              variant={isSidebarCollapsed ? 'icon-only' : 'dark'}
              iconSize={26}
            />
          </NavLink>

          <button
            onClick={toggleSidebar}
            title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 flex items-center justify-center transition-colors cursor-pointer"
          >
            {isSidebarCollapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Section Label */}
        <div className="px-5 pt-5 pb-2">
          {!isSidebarCollapsed ? (
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Research Workspace
            </p>
          ) : (
            <div className="h-[1px] bg-slate-200 my-1" />
          )}
        </div>

        {/* Navigation Links */}
        <nav className="px-3 space-y-1 overflow-y-auto max-h-[calc(100vh-320px)]">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                title={isSidebarCollapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group select-none ${
                    isActive
                      ? 'bg-[#CCFBF1] text-[#0F766E] font-semibold'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  } ${isSidebarCollapsed ? 'justify-center px-0' : ''}`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`w-[18px] h-[18px] shrink-0 transition-colors ${
                        isActive
                          ? 'text-[#0F766E] stroke-[2.2]'
                          : 'text-slate-500 group-hover:text-slate-800 stroke-[1.75]'
                      }`}
                    />
                    {!isSidebarCollapsed && (
                      <span className="truncate">{item.label}</span>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Bottom Section */}
      <div className="p-3 border-t border-slate-100 space-y-3">
        {/* Promo / Info Box (Expanded only) */}
        {!isSidebarCollapsed && (
          <div className="p-3.5 bg-slate-50 border border-slate-200/80 rounded-2xl">
            <h4 className="text-xs font-semibold text-slate-800 leading-tight">
              A clearer path to publication.
            </h4>
            <p className="text-[11px] text-slate-500 mt-1 leading-snug">
              All your research tools, one workspace.
            </p>
          </div>
        )}

        {/* Settings */}
        <NavLink
          to="/settings"
          title={isSidebarCollapsed ? 'Settings' : undefined}
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
              isActive
                ? 'bg-[#CCFBF1] text-[#0F766E]'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            } ${isSidebarCollapsed ? 'justify-center px-0' : ''}`
          }
        >
          <SettingsIcon className="w-[18px] h-[18px] shrink-0 text-slate-500" />
          {!isSidebarCollapsed && <span>Settings</span>}
        </NavLink>

        <div className="h-[1px] bg-slate-200/80 my-1" />

        {/* User Card */}
        {user && (
          <div
            className={`flex items-center gap-3 px-2 py-1.5 rounded-xl ${
              isSidebarCollapsed ? 'justify-center' : ''
            }`}
          >
            <div className="w-8 h-8 rounded-full bg-[#CCFBF1] text-[#0F766E] font-bold text-xs flex items-center justify-center shrink-0 border border-[#99F6E4]">
              {user.avatarInitials}
            </div>
            {!isSidebarCollapsed && (
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-slate-800 truncate">
                  {user.fullName}
                </p>
                <p className="text-[11px] text-slate-400 truncate">
                  {user.role} · {user.plan}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
