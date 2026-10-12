import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, ArrowRight, BookOpen, Check, FileText } from 'lucide-react';
import { PublishAidLogo } from '../components/common/PublishAidLogo';
import { Button } from '../components/common/Button';
import { useApp } from '../context/AppContext';
import { register } from '../lib/api';

function computePasswordStrength(pwd: string): { score: number; label: string; color: string } {
  if (!pwd) return { score: 0, label: '', color: 'text-slate-400' };

  let score = 0;
  if (pwd.length >= 8) score++;
  if (/\d/.test(pwd)) score++;
  if (/[!@#$%^&*(),.?":{}|<>_~`\-+=\\[\]/]/.test(pwd)) score++;
  if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++;

  switch (score) {
    case 1:
      return { score: 1, label: 'Weak', color: 'text-red-500' };
    case 2:
      return { score: 2, label: 'Fair', color: 'text-amber-500' };
    case 3:
      return { score: 3, label: 'Good', color: 'text-teal-600' };
    case 4:
      return { score: 4, label: 'Strong', color: 'text-[#0F766E]' };
    default:
      return { score: 0, label: 'Too weak', color: 'text-slate-400' };
  }
}

export const SignUpPage: React.FC = () => {
  const navigate = useNavigate();
  const { setUser } = useApp();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const passwordStrength = computePasswordStrength(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.');
      return;
    }

    if (!agreeTerms) {
      setErrorMessage('Please agree to the Terms of Service to continue.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await register({ fullName, email, password });
      setUser(res.user);
      navigate('/dashboard');
    } catch (err: any) {
      setErrorMessage(err.message || 'Registration failed. Please try again.');
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
        <div className="my-auto py-6">
          <h1 className="text-3xl sm:text-4xl font-extrabold text-[#14283D] tracking-tight">
            Make room for research.
          </h1>
          <p className="text-slate-500 mt-2 text-sm sm:text-base">
            Create your PublishAid account.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Full name
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Dr. Maya Chen"
                className="w-full px-4 h-[42px] rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Email address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="maya.chen@university.edu"
                className="w-full px-4 h-[42px] rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 pr-11 h-[42px] rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>

              {/* Password strength indicator bars */}
              <div className="mt-2 flex items-center gap-1.5">
                {[1, 2, 3, 4].map((step) => {
                  const active = passwordStrength.score >= step;
                  let barColor = 'bg-slate-200';
                  if (active) {
                    if (passwordStrength.score === 1) barColor = 'bg-red-500';
                    else if (passwordStrength.score === 2) barColor = 'bg-amber-500';
                    else barColor = 'bg-[#0F766E]';
                  }
                  return (
                    <div
                      key={step}
                      className={`h-1 flex-1 rounded-full transition-colors ${barColor}`}
                    />
                  );
                })}
              </div>
              <p className={`text-[11px] mt-1 ${passwordStrength.color}`}>
                {passwordStrength.label ? `${passwordStrength.label} · ` : ''}Must be 8+ characters, with uppercase and lowercase letters, a number, and a symbol.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Confirm password
              </label>
              <div className="relative">
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-4 pr-11 h-[42px] rounded-xl border border-slate-300 text-sm focus:border-[#0F766E] focus:ring-2 focus:ring-[#0F766E]/20 outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <label className="flex items-start gap-2.5 pt-1 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={agreeTerms}
                onChange={(e) => setAgreeTerms(e.target.checked)}
                className="mt-0.5 w-4 h-4 rounded text-[#0F766E] border-slate-300 focus:ring-[#0F766E] cursor-pointer"
              />
              <span className="text-xs text-slate-600 leading-normal">
                I agree to the Terms of Service and Privacy Policy.
              </span>
            </label>

            {errorMessage && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-600 font-medium">
                {errorMessage}
              </div>
            )}

            <Button
              type="submit"
              size="md"
              isLoading={isLoading}
              className="w-full h-[46px] rounded-xl text-base shadow-sm mt-3"
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              Create Account
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-[#0F766E] hover:underline">
              Log In
            </Link>
          </p>
        </div>

        {/* Footer */}
        <div className="text-xs text-slate-400 pt-4">
          © 2026 PublishAid · Privacy · Terms
        </div>
      </div>

      {/* Right Brand Showcase Column */}
      <div className="hidden lg:flex flex-col justify-between bg-[#0D5E4B] text-white p-12 lg:p-16 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-white/5 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <PublishAidLogo variant="light" iconSize={32} />
        </div>

        <div className="relative z-10 max-w-lg my-auto py-10">
          <h2 className="text-4xl xl:text-5xl font-extrabold tracking-tight leading-[1.15]">
            From manuscript to submission, faster.
          </h2>
          <p className="mt-5 text-white/80 text-base leading-relaxed">
            A focused workspace for your next publication. Find the right journal, format with confidence, and submit your best work.
          </p>

          <div className="mt-12 flex items-center gap-4">
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

            <div className="w-9 h-9 rounded-full bg-white/15 flex items-center justify-center shrink-0 text-white backdrop-blur-xs">
              <ArrowRight className="w-4 h-4" />
            </div>

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
