import React, { useState } from 'react';
import { User, Shield, Key, Database, Save, Check, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { Button } from '../components/common/Button';

export const SettingsPage: React.FC = () => {
  const { user, setUser, logout } = useApp();
  const navigate = useNavigate();
  const [name, setName] = useState(user?.fullName || 'Mohib Mansoor');
  const [email, setEmail] = useState(user?.email || 'mohib@publishaid.org');
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (user) {
      setUser({
        ...user,
        fullName: name,
        email,
      });
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-[#14283D] tracking-tight">
          Settings & Account
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Manage your researcher profile, computational preferences, and data privacy options.
        </p>
      </div>

      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-2xs space-y-6">
        <div className="flex items-center gap-4 pb-6 border-b border-slate-100">
          <div className="w-14 h-14 rounded-full bg-[#CCFBF1] text-[#0F766E] font-bold text-lg flex items-center justify-center border border-[#99F6E4]">
            {user?.avatarInitials || 'MM'}
          </div>
          <div>
            <h2 className="text-base font-bold text-[#14283D]">{user?.fullName}</h2>
            <p className="text-xs text-slate-400">{user?.role} · {user?.plan}</p>
          </div>
        </div>

        <form onSubmit={handleSave} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Full name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3.5 h-[42px] rounded-xl border border-slate-200 text-sm focus:border-[#0F766E] outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                University Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 h-[42px] rounded-xl border border-slate-200 text-sm focus:border-[#0F766E] outline-none"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Ephemeral Storage & Data Privacy
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              In accordance with Section 5.4.3 of the PublishAid architecture, all uploaded manuscript binaries (.docx/.tex) are stored temporarily in isolated execution spaces and automatically purged after session termination.
            </p>
          </div>

          <div className="pt-2 flex items-center justify-between flex-wrap gap-3">
            <Button
              type="submit"
              leftIcon={saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            >
              {saved ? 'Changes Saved' : 'Save Changes'}
            </Button>

            <Button
              type="button"
              variant="outline"
              onClick={handleLogout}
              className="text-rose-600 border-rose-200 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-300"
              leftIcon={<LogOut className="w-4 h-4" />}
            >
              Log Out
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
