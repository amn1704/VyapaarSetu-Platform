import { Link, useLocation } from 'react-router-dom';
import { DashboardCircleIcon } from 'hugeicons-react/icons/DashboardCircleIcon';
import { FileLinkIcon } from 'hugeicons-react/icons/FileLinkIcon';
import { FolderShared01Icon } from 'hugeicons-react/icons/FolderShared01Icon';
import { CheckmarkCircle01Icon } from 'hugeicons-react/icons/CheckmarkCircle01Icon';
import { Activity01Icon } from 'hugeicons-react/icons/Activity01Icon';
import { AiSearchIcon } from 'hugeicons-react/icons/AiSearchIcon';
import { GlobeIcon } from 'hugeicons-react/icons/GlobeIcon';
import { Building02Icon } from 'hugeicons-react/icons/Building02Icon';
import { useEffect, useState } from 'react';
import { translations } from '../utils/translations';
import { api } from '../lib/api';

const Layout = ({ children, lang, toggleLang }) => {
  const location = useLocation();
  const [reviewCount, setReviewCount] = useState(0);
  const t = translations[lang];

  // Poll pending review count every 15 seconds
  useEffect(() => {
    const fetchCount = async () => {
      try {
        const data = await api.get('/api/dashboard');
        setReviewCount(data.metrics.pending_review ?? 0);
      } catch (e) {
        console.error('Failed to fetch pending review count', e);
      }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 15000);
    return () => clearInterval(interval);
  }, []);

  const navLinks = [
    { path: '/dashboard', label: t.dashboard, icon: <DashboardCircleIcon size={18} /> },
    { path: '/business-directory', label: t.business_directory || 'Business Directory', icon: <Building02Icon size={18} /> },
    { path: '/raw-records', label: t.raw_records, icon: <FileLinkIcon size={18} /> },
    { path: '/entity-linker', label: t.entity_linker, icon: <FolderShared01Icon size={18} /> },
    { path: '/review', label: t.review_queue, icon: <CheckmarkCircle01Icon size={18} />, badge: reviewCount },
    { path: '/activity-status', label: t.activity_status, icon: <Activity01Icon size={18} /> },
    { path: '/query-engine', label: t.query_engine, icon: <AiSearchIcon size={18} /> },
  ];

  const isLanding = location.pathname === '/';

  const contentClass = isLanding
    ? 'w-full min-w-0'
    : 'w-full max-w-[1440px] mx-auto min-w-0 px-4 py-6 md:px-6 lg:px-8';

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100 overflow-hidden font-sans">
      {/* Left Fixed Sidebar - Hidden on Landing */}
      {!isLanding && (
        <aside className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-950 flex flex-col hidden md:flex">
        <div className="h-16 px-4 flex items-center justify-between border-b border-zinc-800/80">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 flex items-center justify-center">
              <img src="/images/karnataka_gov_logo.png" alt="Logo" className="w-8 h-8 object-contain" />
            </div>
            <div className="flex flex-col">
              <span className="text-lg font-black tracking-tight text-white">VyapaarSetu<span className="text-primary">.</span></span>
            </div>
          </Link>
          
          <button 
            onClick={toggleLang}
            className="p-1.5 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-primary transition-colors text-primary"
            title={lang === 'en' ? 'ಕನ್ನಡಕ್ಕೆ ಬದಲಿಸಿ' : 'Switch to English'}
          >
            <GlobeIcon size={14} />
          </button>
        </div>
        
        <nav className="flex-1 px-4 py-6 space-y-1">
          {navLinks.map((link) => {
            const isActive = location.pathname === link.path;
            return (
              <Link 
                key={link.path} 
                to={link.path}
                className={`flex items-center justify-between px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  isActive 
                    ? 'bg-zinc-800/50 text-white' 
                    : 'text-zinc-400 hover:bg-zinc-800/30 hover:text-zinc-200'
                }`}
              >
                <div className="flex items-center gap-3">
                  {link.icon}
                  {link.label}
                </div>
                {link.badge && (
                  <span className="bg-amber-500 text-zinc-950 text-[10px] font-bold px-2 py-0.5 rounded-full">
                    {link.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </aside>
      )}

      {/* Main Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-zinc-900 overflow-y-auto overflow-x-hidden">
        {!isLanding && (
          <header className="md:hidden sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur">
            <div className="px-4 py-3 flex items-center justify-between gap-4">
              <Link to="/" className="flex items-center gap-3 min-w-0">
                <img src="/images/karnataka_gov_logo.png" alt="Logo" className="w-9 h-9 object-contain shrink-0" />
                <div className="min-w-0">
                  <div className="text-base font-black text-white truncate">VyapaarSetu<span className="text-primary">.</span></div>
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Business registry</div>
                </div>
              </Link>

              <button
                onClick={toggleLang}
                className="h-9 w-9 shrink-0 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-primary transition-colors text-primary flex items-center justify-center"
                title={lang === 'en' ? 'Switch language' : 'Switch to English'}
              >
                <GlobeIcon size={16} />
              </button>
            </div>

            <nav className="px-3 pb-3 flex gap-2 overflow-x-auto no-scrollbar">
              {navLinks.map((link) => {
                const isActive = location.pathname === link.path;
                return (
                  <Link
                    key={link.path}
                    to={link.path}
                    className={`shrink-0 inline-flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-zinc-800 text-white'
                        : 'text-zinc-400 bg-zinc-900/60 hover:text-zinc-200'
                    }`}
                  >
                    {link.icon}
                    <span>{link.label}</span>
                    {link.badge && (
                      <span className="bg-amber-500 text-zinc-950 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                        {link.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </nav>
          </header>
        )}

        {/* Mobile Header with Language Toggle on Landing */}
        {isLanding && (
          <div className="absolute top-8 right-8 z-[100]">
            <button 
              onClick={toggleLang}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-md border border-white/20 hover:bg-white/20 transition-all text-white font-bold text-sm"
            >
              <GlobeIcon size={16} />
              {lang === 'en' ? 'ಕನ್ನಡ' : 'English'}
            </button>
          </div>
        )}

        <div className={contentClass}>
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
