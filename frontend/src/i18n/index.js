import { useMemo, useState } from 'react';
import { translations } from '../utils/translations';

const STORAGE_KEY = 'vyapaarsetu_lang';
const LEGACY_STORAGE_KEY = 'eka_vyapara_lang';
const SUPPORTED_LANGS = new Set(['en', 'kn']);

function resolveInitialLang() {
  const saved = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY) || 'en';
  return SUPPORTED_LANGS.has(saved) ? saved : 'en';
}

export function useI18n() {
  const [lang, setLang] = useState(resolveInitialLang);

  const t = useMemo(() => {
    const active = translations[lang] || translations.en;
    return (key, fallback = '') => active[key] || translations.en[key] || fallback || key;
  }, [lang]);

  const setLanguage = (next) => {
    const safeLang = SUPPORTED_LANGS.has(next) ? next : 'en';
    setLang(safeLang);
    localStorage.setItem(STORAGE_KEY, safeLang);
  };

  const toggleLang = () => {
    setLanguage(lang === 'en' ? 'kn' : 'en');
  };

  return { lang, t, setLanguage, toggleLang };
}
