import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, Search } from 'lucide-react';

export interface DropdownOption<T = string | number> {
  value: T;
  label: string;
  sublabel?: string;
  badge?: string;
  disabled?: boolean;
}

export interface CustomDropdownProps<T = string | number> {
  value: T;
  onChange: (value: T) => void;
  options: (DropdownOption<T> | string | number)[];
  placeholder?: string;
  label?: string;
  badge?: React.ReactNode;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  searchable?: boolean;
  searchPlaceholder?: string;
  className?: string;
  triggerClassName?: string;
  menuClassName?: string;
}

export function CustomDropdown<T extends string | number = string>({
  value,
  onChange,
  options,
  placeholder = 'Select an option...',
  label,
  badge,
  disabled = false,
  size = 'md',
  fullWidth = true,
  searchable = false,
  searchPlaceholder = 'Search...',
  className = '',
  triggerClassName = '',
  menuClassName = '',
}: CustomDropdownProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Normalize options to DropdownOption format
  const normalizedOptions: DropdownOption<T>[] = options.map((opt) => {
    if (typeof opt === 'object' && opt !== null && 'value' in opt) {
      return opt as DropdownOption<T>;
    }
    return {
      value: opt as T,
      label: String(opt),
    };
  });

  const selectedOption = normalizedOptions.find((opt) => opt.value === value);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Focus search input when opened
  useEffect(() => {
    if (isOpen && searchable && searchInputRef.current) {
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    }
    if (!isOpen) {
      setSearchQuery('');
    }
  }, [isOpen, searchable]);

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const filteredOptions = searchable && searchQuery.trim()
    ? normalizedOptions.filter((opt) =>
        opt.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (opt.sublabel && opt.sublabel.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : normalizedOptions;

  const sizeClasses = {
    sm: 'h-[34px] px-3 text-xs rounded-lg',
    md: 'h-[40px] px-3.5 text-xs sm:text-sm rounded-xl',
    lg: 'h-[44px] px-4 text-sm rounded-xl',
  };

  const handleSelect = (opt: DropdownOption<T>) => {
    if (opt.disabled) return;
    onChange(opt.value);
    setIsOpen(false);
  };

  return (
    <div
      ref={dropdownRef}
      className={`relative text-left ${fullWidth ? 'w-full' : 'inline-block'} ${className}`}
    >
      {label && (
        <div className="flex items-center justify-between mb-1.5">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
            {label}
          </label>
          {badge}
        </div>
      )}

      {/* Trigger Button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen((prev) => !prev)}
        className={`
          w-full flex items-center justify-between gap-2.5 font-medium text-slate-800 bg-white
          border border-slate-200/90 shadow-2xs hover:border-slate-300 hover:bg-slate-50/60
          focus:border-[#0F766E] focus:ring-4 focus:ring-[#0F766E]/10 outline-none
          transition-all duration-150 cursor-pointer select-none text-left
          disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed
          ${sizeClasses[size]}
          ${isOpen ? 'border-[#0F766E] ring-4 ring-[#0F766E]/10' : ''}
          ${triggerClassName}
        `}
      >
        <span className="truncate flex-1">
          {selectedOption ? selectedOption.label : <span className="text-slate-400">{placeholder}</span>}
        </span>
        <ChevronDown
          className={`w-4 h-4 text-slate-400 shrink-0 transition-transform duration-200 ${
            isOpen ? 'rotate-180 text-[#0F766E]' : ''
          }`}
        />
      </button>

      {/* Dropdown Menu Card */}
      {isOpen && (
        <div
          className={`
            absolute left-0 mt-1.5 w-full min-w-[200px] z-50
            bg-white rounded-xl border border-slate-200 shadow-xl shadow-slate-900/10
            py-1.5 overflow-hidden transition-all duration-150 animate-in fade-in-0 zoom-in-95
            ${menuClassName}
          `}
        >
          {/* Search bar inside dropdown if enabled */}
          {searchable && (
            <div className="px-2 pb-1.5 pt-0.5 border-b border-slate-100">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={searchPlaceholder}
                  className="w-full pl-8 pr-3 h-[32px] text-xs bg-slate-50 rounded-lg border border-slate-200 outline-none focus:border-[#0F766E] focus:bg-white text-slate-800 placeholder:text-slate-400"
                  onClick={(e) => e.stopPropagation()}
                />
              </div>
            </div>
          )}

          {/* Options List */}
          <div className="max-h-60 overflow-y-auto overflow-x-hidden p-1 space-y-0.5 custom-scrollbar">
            {filteredOptions.length === 0 ? (
              <div className="py-3 px-3 text-center text-xs text-slate-400">
                No options found
              </div>
            ) : (
              filteredOptions.map((opt) => {
                const isSelected = opt.value === value;
                return (
                  <button
                    key={String(opt.value)}
                    type="button"
                    disabled={opt.disabled}
                    onClick={() => handleSelect(opt)}
                    className={`
                      w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-left text-xs sm:text-sm font-medium
                      transition-colors cursor-pointer select-none
                      ${
                        isSelected
                          ? 'bg-teal-50 text-[#0F766E] font-semibold'
                          : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
                      }
                      ${opt.disabled ? 'opacity-40 cursor-not-allowed' : ''}
                    `}
                  >
                    <div className="flex flex-col truncate flex-1">
                      <span className="truncate">{opt.label}</span>
                      {opt.sublabel && (
                        <span className={`text-[11px] truncate ${isSelected ? 'text-teal-600/80' : 'text-slate-400'}`}>
                          {opt.sublabel}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {opt.badge && (
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                          {opt.badge}
                        </span>
                      )}
                      {isSelected && (
                        <Check className="w-4 h-4 text-[#0F766E] shrink-0 stroke-[2.5]" />
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

