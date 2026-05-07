import { useCallback, useEffect, useState } from 'react';
import { CheckmarkCircle01Icon } from 'hugeicons-react/icons/CheckmarkCircle01Icon';
import { Cancel01Icon } from 'hugeicons-react/icons/Cancel01Icon';
import { AlarmClockIcon } from 'hugeicons-react/icons/AlarmClockIcon';
import { AlertCircleIcon } from 'hugeicons-react/icons/AlertCircleIcon';
import { translations } from '../utils/translations';
import { api } from '../lib/api';

const reviewFields = (t) => [
  [t.source_id, 'id'],
  [t.business_name, 'name'],
  [t.address, 'address'],
  [t.pan, 'pan'],
  [t.gst_number, 'gstin'],
  [t.pin_code, 'pincode'],
  [t.business_type, 'sector']
];

const titleCase = (value) => String(value || '').toLowerCase().replace(/\b\w/g, char => char.toUpperCase());

const plainReason = (value) => {
  if (value === 'pan_match') return 'same PAN';
  if (value === 'gstin_match') return 'same GSTIN';
  if (value === 'pincode_name') return 'same PIN code and similar name';
  if (value === 'phonetic_window') return 'similar sounding name';
  return String(value || 'possible match').replace(/_/g, ' ');
};

const ReviewQueue = ({ lang }) => {
  const t = translations[lang || 'en'];
  const [items, setItems] = useState([]);
  const [summaries, setSummaries] = useState({});
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
  };

  const fetchQueue = useCallback(() => {
    setLoading(true);
    return api.get('/api/review-queue')
      .then(data => setItems(Array.isArray(data) ? data : []))
      .catch(err => {
        console.error('Failed to fetch review queue', err);
        setItems([]);
        showToast('Could not load review cases. Please check the backend.', 'warning');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  useEffect(() => {
    let cancelled = false;
    const loadSummaries = async () => {
      for (const item of items) {
        if (cancelled) continue;
        try {
          setSummaries(prev => ({
            ...prev,
            [item.id]: { summary: item.summary || 'Preparing short summary...', source: 'rule_summary' }
          }));
          const data = await api.get(`/api/review-queue/${item.id}/summary`);
          if (!cancelled) {
            setSummaries(prev => ({ ...prev, [item.id]: data }));
          }
        } catch {
          if (!cancelled) {
            setSummaries(prev => ({
              ...prev,
              [item.id]: { summary: item.summary || 'Please compare the records below before deciding.', source: 'rule_summary' }
            }));
          }
        }
      }
    };
    if (items.length > 0) loadSummaries();
    return () => {
      cancelled = true;
    };
  }, [items]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(timer);
  }, [toast]);

  const handleAction = (decision, queueItemId) => {
    setActingId(queueItemId);
    api.post('/api/review-queue/action', {
      queue_item_id: queueItemId,
      decision,
      reviewer_id: 'admin',
      justification: decision === 'confirm_non_match' ? 'Reviewed and manually separated by admin.' : ''
    })
      .then(data => fetchQueue().then(() => data))
      .then(data => {
        if (decision === 'confirm_match') {
          showToast(`Merge approved${data.ubid ? `: ${data.ubid}` : ''}. Links and business status updated.`, 'success');
        } else if (decision === 'confirm_non_match') {
          showToast('Records kept separate. Training label saved.', 'warning');
        } else {
          showToast(`Review moved to later. ${data.pending_count ?? items.length} cases pending.`, 'info');
        }
      })
      .catch(err => {
        console.error('Failed to post review action', err);
        showToast(`Could not save review decision: ${err.message}`, 'warning');
      })
      .finally(() => setActingId(null));
  };

  return (
    <div className="space-y-6 relative">
      {toast && (
        <div className={`absolute top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300 animate-in fade-in slide-in-from-top-4 ${
          toast.type === 'success' ? 'bg-emerald-950/90 border-emerald-900 text-emerald-400' :
          toast.type === 'warning' ? 'bg-rose-950/90 border-rose-900 text-rose-400' :
          'bg-zinc-800 border-zinc-700 text-zinc-300'
        }`}>
          {toast.type === 'success' && <CheckmarkCircle01Icon size={18} />}
          {toast.type === 'warning' && <AlertCircleIcon size={18} />}
          {toast.type === 'info' && <AlarmClockIcon size={18} />}
          <span className="text-sm font-medium">{toast.message}</span>
        </div>
      )}

      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 mb-2">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">{t.review_queue}</h1>
          <p className="text-zinc-400 text-sm">{t.review_queue_subtitle}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={fetchQueue}
            disabled={loading}
            className="px-3 py-1.5 rounded-md bg-zinc-900 border border-zinc-800 text-sm font-medium text-zinc-300 hover:text-white disabled:opacity-60"
          >
            {loading ? t.loading : t.refresh}
          </button>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-zinc-900 border border-zinc-800 text-sm font-medium text-zinc-300">
            <AlertCircleIcon size={16} className={items.length > 0 ? 'text-accent' : 'text-emerald-500'} />
            {items.length} {t.pending}
          </div>
        </div>
      </div>

      {loading && items.length === 0 ? (
        <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-16 flex flex-col items-center justify-center text-center">
          <div className="w-8 h-8 border-2 border-zinc-700 border-t-primary rounded-full animate-spin mb-4" />
          <p className="text-zinc-400">{t.loading_cases}</p>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-16 flex flex-col items-center justify-center text-center">
          <CheckmarkCircle01Icon size={48} className="text-emerald-500 mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">{t.queue_empty}</h2>
          <p className="text-zinc-400">{t.all_resolved}</p>
        </div>
      ) : (
        <div className="space-y-6">
          {items.map(item => (
            <div key={item.id} className="bg-zinc-950 border border-zinc-800 border-l-[3px] border-l-accent rounded-xl overflow-hidden flex flex-col shadow-sm">
              <div className="p-6 pb-5">
                <div className="flex flex-col xl:flex-row xl:justify-between xl:items-start gap-5 mb-6">
                  <div className="min-w-0">
                    <p className="text-[10px] text-zinc-500 font-bold tracking-widest mb-1 uppercase">{t.review_case}</p>
                    <h2 className="text-[22px] font-bold text-white leading-tight mb-1">{item.recordA.name}</h2>
                    <div className="flex flex-wrap gap-2 text-xs text-zinc-400">
                      <span className="font-mono">{item.recordA.id}</span>
                      <span>{t.found_because}: {plainReason(item.blocking_strategy)}</span>
                      <span>{t.urgency} {item.priority ?? 0}</span>
                      {item.queued_at && <span>{t.queued} {item.queued_at}</span>}
                    </div>
                  </div>
                  <div className="xl:text-right shrink-0">
                    <p className="text-[10px] text-zinc-500 mb-1">{t.system_confidence}</p>
                    <p className="text-[28px] font-bold text-accent leading-none">{item.confidence_score}%</p>
                    <p className="text-xs text-zinc-500 mt-1">{item.evidence?.band || t.needs_officer_check}</p>
                  </div>
                </div>

                <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 mb-5">
                  <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-2">{t.officer_summary}</p>
                  <p className="text-sm text-zinc-200 leading-relaxed">
                    {summaries[item.id]?.summary || item.summary || 'Preparing short summary...'}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <PlainFact ok={item.evidence?.matches?.pan} label={t.pan} t={t} />
                    <PlainFact ok={item.evidence?.matches?.gstin} label={t.gst_number} t={t} />
                    <PlainFact ok={item.evidence?.matches?.pincode} label={t.pin_code} t={t} />
                    <PlainFact ok={item.evidence?.matches?.sector} label={t.business_type} t={t} />
                  </div>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-6">
                  <ReviewPanel title={t.why_it_may_be_same} items={item.evidence?.signals || []} tone="success" empty={t.no_strong_reason} />
                  <ReviewPanel title={t.what_to_check} items={item.evidence?.cautions || []} tone="warning" empty={t.no_warning} />
                  <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg p-4">
                    <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-3">{t.common_name_words}</p>
                    <div className="flex flex-wrap gap-2">
                      {(item.evidence?.token_overlap?.shared_name_tokens || []).length > 0 ? (
                        item.evidence.token_overlap.shared_name_tokens.map(token => (
                          <span key={token} className="px-2 py-1 rounded bg-zinc-950 border border-zinc-800 text-xs text-zinc-300 normal-case">{titleCase(token)}</span>
                        ))
                      ) : (
                        <span className="text-xs text-zinc-500">{t.no_common_words}</span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-500 mt-3">
                      {t.name_similarity} {item.evidence?.token_overlap?.name ?? 0}% / {t.address_similarity} {item.evidence?.token_overlap?.address ?? 0}%
                    </p>
                  </div>
                </div>

                <div className="mb-8 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950/50">
                  <table className="w-full text-left text-xs border-collapse min-w-[800px]">
                    <thead>
                      <tr className="bg-zinc-900 text-zinc-400 border-b border-zinc-800">
                        <th className="px-6 py-4 font-bold w-48 uppercase tracking-widest text-[9px]">{t.field}</th>
                        <th className="px-6 py-4 font-bold border-l border-zinc-800 uppercase tracking-widest text-[10px] text-zinc-100">{item.recordA.source}</th>
                        <th className="px-6 py-4 font-bold border-l border-zinc-800 uppercase tracking-widest text-[10px] text-zinc-100">{item.recordB.source}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50">
                      {reviewFields(t).map(([label, key]) => (
                        <tr key={key} className="hover:bg-zinc-900/30 transition-colors">
                          <td className="px-6 py-4 font-bold text-zinc-500 bg-zinc-900/10">{label}</td>
                          <td className="px-6 py-4 border-l border-zinc-800 font-medium text-zinc-200">{item.recordA[key]}</td>
                          <td className={`px-6 py-4 border-l border-zinc-800 font-medium ${item.recordA[key] === item.recordB[key] && item.recordB[key] !== 'N/A' ? 'text-emerald-400' : 'text-zinc-200'}`}>{item.recordB[key]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-zinc-800 bg-zinc-900/50 flex flex-wrap gap-3">
                <button
                  onClick={() => handleAction('confirm_match', item.id)}
                  disabled={actingId === item.id}
                  className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 disabled:cursor-wait text-white rounded-md text-sm font-medium transition-colors shadow-sm"
                >
                  <CheckmarkCircle01Icon size={16} /> {actingId === item.id ? t.saving : t.same_business}
                </button>
                <button
                  onClick={() => handleAction('confirm_non_match', item.id)}
                  disabled={actingId === item.id}
                  className="flex items-center gap-1.5 px-4 py-2 bg-rose-950/20 hover:bg-rose-950/40 disabled:opacity-60 border border-rose-900/50 text-rose-400 rounded-md text-sm font-medium transition-colors"
                >
                  <Cancel01Icon size={16} /> {t.different_business}
                </button>
                <button
                  onClick={() => handleAction('defer', item.id)}
                  disabled={actingId === item.id}
                  className="flex items-center gap-1.5 px-4 py-2 bg-zinc-950 hover:bg-zinc-900 disabled:opacity-60 border border-zinc-800 text-zinc-300 rounded-md text-sm font-medium transition-colors"
                >
                  <AlarmClockIcon size={16} /> {t.review_later}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const ReviewPanel = ({ title, items, tone, empty }) => {
  const iconClass = tone === 'success' ? 'text-emerald-400' : 'text-amber-400';
  return (
    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg p-4">
      <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-3">{title}</p>
      <div className="space-y-2">
        {items.length === 0 ? (
          <p className="text-xs text-zinc-500">{empty}</p>
        ) : (
          items.map((item, index) => (
            <div key={`${item}-${index}`} className="flex gap-2 text-xs text-zinc-300 leading-relaxed">
              <CheckmarkCircle01Icon size={14} className={`${iconClass} shrink-0 mt-0.5`} />
              <span>{item}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

const PlainFact = ({ ok, label, t }) => (
  <span className={`px-2.5 py-1 rounded border text-xs font-semibold ${
    ok
      ? 'bg-emerald-500/10 border-emerald-900/60 text-emerald-300'
      : 'bg-zinc-950 border-zinc-800 text-zinc-400'
  }`}>
    {label}: {ok ? (t?.same || 'same') : (t?.check || 'check')}
  </span>
);

export default ReviewQueue;
