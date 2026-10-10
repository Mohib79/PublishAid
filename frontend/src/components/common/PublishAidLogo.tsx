import React from 'react';

interface PublishAidLogoProps {
  className?: string;
  variant?: 'dark' | 'light' | 'icon-only';
  iconSize?: number;
}

export const PublishAidLogo: React.FC<PublishAidLogoProps> = ({
  className = '',
  variant = 'dark',
  iconSize = 28,
}) => {
  const isLight = variant === 'light';

  return (
    <div className={`flex items-center gap-2.5 font-bold tracking-tight select-none ${className}`}>
      {/* Signature Folded Document with Upward Arrow */}
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 28 28"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0"
      >
        {/* Document Outline with folded top-right corner */}
        <path
          d="M6 3.5C4.61929 3.5 3.5 4.61929 3.5 6V22C3.5 23.3807 4.61929 24.5 6 24.5H22C23.3807 24.5 24.5 23.3807 24.5 22V10L18 3.5H6Z"
          stroke={isLight ? '#FFFFFF' : '#0F766E'}
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Fold line */}
        <path
          d="M18 3.5V10H24.5"
          stroke={isLight ? '#FFFFFF' : '#0F766E'}
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Upward progress arrow inside */}
        <path
          d="M14 19V11M14 11L10.5 14.5M14 11L17.5 14.5"
          stroke={isLight ? '#FFFFFF' : '#0F766E'}
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {variant !== 'icon-only' && (
        <span
          className={`text-xl font-bold tracking-tight ${
            isLight ? 'text-white' : 'text-[#14283D]'
          }`}
        >
          Publish<span className={isLight ? 'text-[#99F6E4]' : 'text-[#0F766E]'}>Aid</span>
        </span>
      )}
    </div>
  );
};
