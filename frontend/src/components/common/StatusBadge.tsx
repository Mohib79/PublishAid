import React from 'react';

export type BadgeVariant =
  | 'Completed'
  | 'Needs review'
  | 'Failed'
  | 'Draft'
  | 'Q1'
  | 'Q2'
  | 'Q3'
  | 'Q4'
  | 'Formatting'
  | 'Ready to submit'
  | 'Open access'
  | 'Hybrid'
  | 'Template ready'
  | 'Summary complete'
  | 'Passed';

interface StatusBadgeProps {
  status: BadgeVariant | string;
  className?: string;
  dot?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '', dot = false }) => {
  let bgStyles = 'bg-slate-100 text-slate-700 border-slate-200';
  let dotColor = 'bg-slate-400';

  const s = status.toLowerCase();

  if (s.includes('completed') || s.includes('passed') || s.includes('template ready') || s.includes('summary complete')) {
    bgStyles = 'bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]';
    dotColor = 'bg-[#15803D]';
  } else if (s.includes('needs review')) {
    bgStyles = 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]';
    dotColor = 'bg-[#B45309]';
  } else if (s.includes('failed')) {
    bgStyles = 'bg-[#FEE2E2] text-[#B91C1C] border-[#FECACA]';
    dotColor = 'bg-[#B91C1C]';
  } else if (s.includes('ready to submit')) {
    bgStyles = 'bg-[#D1FAE5] text-[#0F766E] border-[#A7F3D0]';
    dotColor = 'bg-[#0F766E]';
  } else if (s.includes('formatting')) {
    bgStyles = 'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]';
    dotColor = 'bg-[#0369A1]';
  } else if (s.includes('q1')) {
    bgStyles = 'bg-[#CCFBF1] text-[#0F766E] border-[#99F6E4] font-semibold';
    dotColor = 'bg-[#0F766E]';
  } else if (s.includes('q2')) {
    bgStyles = 'bg-blue-50 text-blue-700 border-blue-200';
    dotColor = 'bg-blue-600';
  } else if (s.includes('open access')) {
    bgStyles = 'bg-[#F0FDF4] text-[#16A34A] border-[#DCFCE7]';
    dotColor = 'bg-[#16A34A]';
  } else if (s.includes('hybrid')) {
    bgStyles = 'bg-slate-100 text-slate-600 border-slate-200';
    dotColor = 'bg-slate-500';
  } else if (s.includes('draft')) {
    bgStyles = 'bg-slate-100 text-slate-600 border-slate-200';
    dotColor = 'bg-slate-400';
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${bgStyles} ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />}
      {status}
    </span>
  );
};
