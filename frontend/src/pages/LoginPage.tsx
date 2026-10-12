import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, ArrowRight, BookOpen, Check, FileText } from 'lucide-react';
import { PublishAidLogo } from '../components/common/PublishAidLogo';
import { Button } from '../components/common/Button';
import { useApp } from '../context/AppContext';

import { login } from '../lib/api';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { setUser } = useApp();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const res = await login({ email, password });
      setUser(res.user);
      navigate('/dashboard');
    } catch (err: any) {
      setErrorMessage(err.message || 'Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-white">
      {/* Left Form Column */}
      <div className="flex flex-col justify-between p-8 sm:p-12 lg:p-16 max-w-xl w-full mx-auto">
        {/* Top Logo */}
        <div>
          <PublishAidLogo iconSize={32} />
        </div>

        {/* Center Content */}
        <div className="my-auto py-8">
          <h1 className="text-3xl sm:text-4xl font-extrabold text-[#14283D] tracking-tight">
            Welcome back.
          </h1>
          <p className="text-slate-500 mt-2 text-sm sm:text-base">
            Log in to your research workspace.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Email address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@university.edu"
                className="w-full px-4 h-[44px] rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 pr-11 h-[44px] rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex justify-end">
              <a
                href="#forgot"
                onClick={(e) => {
                  e.preventDefault();
                  alert('Password reset instructions will be sent to your registered university email.');
                }}
                className="text-xs font-semibold text-[#0F766E] hover:underline"
              >
                Forgot password?
              </a>
            </div>

            {errorMessage && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-600 font-medium">
                {errorMessage}
              </div>
            )}

            <Button
              type="submit"
              size="md"
              isLoading={isLoading}
              className="w-full h-[46px] rounded-xl text-base shadow-sm"
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              Log In
            </Button>
          </form>

          <p className="mt-8 text-center text-sm text-slate-500">
            New to PublishAid?{' '}
            <Link to="/signup" className="font-semibold text-[#0F766E] hover:underline">
              Sign Up
            </Link>
          </p>
        </div>

        {/* Footer */}
        <div className="text-xs text-slate-400 pt-6">
          © 2026 PublishAid · Privacy · Terms
        </div>
      </div>

      {/* Right Brand Showcase Column */}
      <div className="hidden lg:flex flex-col justify-between bg-[#0D5E4B] text-white p-12 lg:p-16 relative overflow-hidden">
        {/* Subtle background graphic */}
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-white/5 rounded-full blur-3xl pointer-events-none" />

        {/* Top Logo */}
        <div className="relative z-10">
          <PublishAidLogo variant="light" iconSize={32} />
        </div>

        {/* Middle Value Proposition & Interactive Mock Cards */}
        <div className="relative z-10 max-w-lg my-auto py-10">
          <h2 className="text-4xl xl:text-5xl font-extrabold tracking-tight leading-[1.15]">
            From manuscript to submission, faster.
          </h2>
          <p className="mt-5 text-white/80 text-base leading-relaxed">
            A focused workspace for your next publication. Find the right journal, format with confidence, and submit your best work.
          </p>

          {/* Cards Graphic */}
          <div className="mt-12 flex items-center gap-4">
            {/* Manuscript Card */}
            <div className="w-[180px] bg-white text-[#14283D] rounded-2xl p-4 shadow-xl border border-white/20">
              <div className="flex items-center gap-2 text-[#0F766E] text-xs font-bold uppercase tracking-wider">
                <FileText className="w-3.5 h-3.5" />
                <span>MANUSCRIPT</span>
              </div>
              <div className="mt-3 space-y-1.5">
                <div className="h-2 bg-[#99F6E4]/70 rounded w-full" />
                <div className="h-1.5 bg-slate-200 rounded w-4/5" />
                <div className="h-1.5 bg-slate-200 rounded w-full" />
                <div className="h-1.5 bg-slate-200 rounded w-3/4" />
                <div className="h-1.5 bg-slate-200 rounded w-5/6" />
              </div>
              <div className="mt-5 pt-2 border-t border-slate-100 flex justify-center">
                <span className="text-[10px] font-semibold text-[#0F766E] bg-[#CCFBF1] px-2 py-0.5 rounded-full">
                  Ready to format
                </span>
              </div>
            </div>

            {/* Connecting Arrow */}
            <div className="w-9 h-9 rounded-full bg-white/15 flex items-center justify-center shrink-0 text-white backdrop-blur-xs">
              <ArrowRight className="w-4 h-4" />
            </div>

            {/* Publication Card */}
            <div className="w-[180px] bg-[#CCFBF1] text-[#14283D] rounded-2xl p-4 shadow-xl border border-[#99F6E4]">
              <div className="w-8 h-8 rounded-lg bg-white/60 flex items-center justify-center text-[#0F766E]">
                <BookOpen className="w-4 h-4" />
              </div>
              <h4 className="mt-3 font-bold text-sm text-[#0B4638] leading-snug">
                Your next publication.
              </h4>
              <div className="mt-5 pt-2 border-t border-[#99F6E4]/60 flex items-center gap-1.5 text-[10px] font-semibold text-[#0F766E]">
                <div className="w-3.5 h-3.5 rounded-full bg-[#0F766E] text-white flex items-center justify-center text-[8px]">
                  <Check className="w-2.5 h-2.5 stroke-[3]" />
                </div>
                <span>Submission ready</span>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Tag */}
        <div className="relative z-10 text-xs text-white/70 space-y-1">
          <p className="font-semibold uppercase tracking-wider text-[11px] text-[#99F6E4]">
            BUILT FOR THE WAY RESEARCHERS WORK
          </p>
          <p className="text-white/90">Discover. Prepare. Publish.</p>
        </div>
      </div>
    </div>
  );
};
