import React from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'mint';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className = '',
  disabled,
  ...props
}) => {
  // Height 42px is default for md in Figma design kit
  const sizeClasses = {
    sm: 'h-8 px-3 text-xs rounded-lg',
    md: 'h-[42px] px-4 text-sm font-medium rounded-lg',
    lg: 'h-12 px-6 text-base font-medium rounded-xl',
  };

  const variantClasses = {
    primary:
      'bg-[#0F766E] hover:bg-[#0D5E4B] text-white shadow-sm transition-all duration-150 active:scale-[0.98]',
    secondary:
      'bg-white hover:bg-slate-50 text-[#14283D] border border-slate-200 shadow-xs transition-all duration-150 active:scale-[0.98]',
    outline:
      'bg-transparent hover:bg-slate-100 text-[#14283D] border border-slate-300 transition-all duration-150',
    ghost:
      'bg-transparent hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-all duration-150',
    mint:
      'bg-[#CCFBF1] hover:bg-[#99F6E4] text-[#0F766E] font-semibold border border-[#99F6E4]/60 transition-all duration-150',
  };

  return (
    <button
      disabled={disabled || isLoading}
      className={`inline-flex items-center justify-center gap-2 select-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin text-current" />
      ) : (
        leftIcon && <span className="shrink-0">{leftIcon}</span>
      )}
      <span>{children}</span>
      {!isLoading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
    </button>
  );
};
