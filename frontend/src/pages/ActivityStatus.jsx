import { useState, useEffect } from 'react';
import { Activity01Icon } from 'hugeicons-react/icons/Activity01Icon';
import { DatabaseLightningIcon } from 'hugeicons-react/icons/DatabaseLightningIcon';
import { AiSearchIcon } from 'hugeicons-react/icons/AiSearchIcon';
import { Loading01Icon } from 'hugeicons-react/icons/Loading01Icon';
import { CancelCircleIcon } from 'hugeicons-react/icons/CancelCircleIcon';
import { CheckmarkCircle01Icon } from 'hugeicons-react/icons/CheckmarkCircle01Icon';
import { useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';

const fmt = (value) => {
  if (value === null || value === undefined || value === '') return 'N/A';
  return String(value);
};

const joinValues = (values) => {
  if (!Array.isArray(values) || values.length === 0) return 'N/A';
  return values.filter(Boolean).join(', ') || 'N/A';
};

const fmtScore = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return 'N/A';
  return number.toFixed(2);
};

const recordIdOf = (record) => record?.source_record_id || record?.id || 'N/A';

const statusColor = (status) => {
  if (status === 'Active') return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
  if (status === 'Dormant') return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
  if (status === 'Closed') return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
  return 'text-zinc-300 bg-zinc-800 border-zinc-700';
};

const eventStyle = (type) => {
  if (type === 'computed') return { dot: 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]', icon: 'text-emerald-500', label: 'Computed' };
  if (type === 'review') return { dot: 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.35)]', icon: 'text-amber-500', label: 'Review' };
  if (type === 'link') return { dot: 'bg-primary shadow-[0_0_10px_rgba(30,77,140,0.45)]', icon: 'text-primary', label: 'Link' };
  return { dot: 'bg-zinc-600', icon: 'text-zinc-400', label: 'Signal' };
};

const ActivityStatus = () => {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('ubid') || '');
  const [isSearching, setIsSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);

  const triggerSearch = (ubid) => {
    if (!ubid) return;
    setIsSearching(true);
    setHasSearched(true);
    setError(null);
    setResult(null);

    api.get('/api/entity/activity', { params: { ubid } })
      .then(data => {
        setResult(data);
        setIsSearching(false);
      })
      .catch(err => {
        console.error('Lookup failed', err);
        setError(err.message);
        setIsSearching(false);
      });
  };

  useEffect(() => {
    const ubidFromUrl = searchParams.get('ubid');
    if (ubidFromUrl) {
      setQuery(ubidFromUrl);
      triggerSearch(ubidFromUrl);
    }
  }, [searchParams]);

  const handleSearch = (e) => {
    if (e) e.preventDefault();
    triggerSearch(query);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col mb-2">
        <h1 className="text-2xl font-bold text-white mb-1">Business Status</h1>
        <p className="text-zinc-400 text-sm">
          Enter a VyapaarSetu business ID to see linked department records and recent activity.
        </p>
      </div>

      <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6 shadow-sm">
        <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4 max-w-3xl">
          <div className="relative flex-1">
            <AiSearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={18} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter business ID, e.g. UBID-KA-29-2026-000085-1"
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg py-2.5 pl-10 pr-4 text-sm text-zinc-100 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all placeholder:text-zinc-600"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching}
            className="flex items-center justify-center gap-2 px-6 py-2.5 bg-primary hover:bg-primary/90 disabled:bg-primary/50 text-white rounded-lg font-medium transition-colors shadow-sm whitespace-nowrap"
          >
            {isSearching ? <Loading01Icon size={16} className="animate-spin" /> : <Activity01Icon size={16} />}
            Check Status
          </button>
        </form>
      </div>

      {isSearching && (
        <div className="flex flex-col items-center justify-center p-12 text-zinc-500">
          <Loading01Icon size={32} className="animate-spin mb-4 text-primary" />
          <p>Checking business activity...</p>
        </div>
      )}

      {error && !isSearching && (
        <div className="bg-red-950/20 border border-red-900/50 rounded-xl p-8 flex flex-col items-center justify-center text-center animate-in fade-in slide-in-from-top-4">
          <div className="w-12 h-12 bg-red-900/30 rounded-full flex items-center justify-center mb-4">
            <CancelCircleIcon className="text-red-500" size={24} />
          </div>
          <h3 className="text-lg font-bold text-white mb-2">Business ID Not Found</h3>
          <p className="text-zinc-400 max-w-md mx-auto">Please enter a valid VyapaarSetu business ID.</p>
        </div>
      )}

      {hasSearched && !isSearching && result && result.ubid && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5">
              <div>
                <div className="text-xs text-primary font-bold mb-1 font-mono">{result.ubid}</div>
                <h2 className="text-2xl font-bold text-white">{result.name}</h2>
                <p className="text-sm text-zinc-400 mt-1">{fmt(result.details?.address)}</p>
              </div>
              <div className={`w-fit px-3 py-1.5 rounded-full border text-xs font-bold uppercase ${statusColor(result.status)}`}>
                {result.status}
              </div>
            </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mt-6">
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <div className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">Activity Score</div>
                <div className="text-2xl font-bold text-white mt-1">{fmtScore(result.score)}</div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <div className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">Records Linked</div>
                <div className="text-2xl font-bold text-white mt-1">{result.summary?.source_records || result.source_count || 0}</div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <div className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">Departments</div>
                <div className="text-2xl font-bold text-white mt-1">{result.summary?.linked_departments || 0}</div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <div className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">Checked On</div>
                <div className="text-sm font-mono text-zinc-200 mt-2">{fmt(result.computed_at)}</div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)] gap-6">
            <div className="space-y-6 min-w-0">
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
                <h3 className="text-white font-bold mb-5">Business Profile</h3>
                <div className="space-y-4">
                  {[
                    ['PAN', fmt(result.details?.pan)],
                    ['GSTIN', fmt(result.details?.gstin)],
                    ['Sector', fmt(result.details?.sector)],
                    ['All sectors', joinValues(result.details?.sectors)],
                    ['Pincode', joinValues(result.details?.pincodes)],
                    ['Proprietor', fmt(result.details?.proprietor)],
                    ['Created', fmt(result.created_at)],
                    ['Updated', fmt(result.updated_at)]
                  ].map(([label, value]) => (
                    <div key={label}>
                      <div className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider mb-1">{label}</div>
                      <div className="text-sm text-zinc-200 break-words">{value}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
                <h3 className="text-white font-bold mb-5">Identifier Check</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400">PAN mismatch</span>
                    <span className={result.summary?.identifier_conflicts?.pan ? 'text-rose-400' : 'text-emerald-400'}>
                      {result.summary?.identifier_conflicts?.pan ? 'Yes' : 'No'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400">GSTIN mismatch</span>
                    <span className={result.summary?.identifier_conflicts?.gstin ? 'text-rose-400' : 'text-emerald-400'}>
                      {result.summary?.identifier_conflicts?.gstin ? 'Yes' : 'No'}
                    </span>
                  </div>
                  <div className="pt-3 border-t border-zinc-800">
                    <div className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider mb-1">Department systems</div>
                    <div className="flex flex-wrap gap-2">
                      {(result.details?.source_systems || []).map(source => (
                        <span key={source} className="px-2 py-1 bg-zinc-900 border border-zinc-800 rounded text-xs text-zinc-300">{source}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-6 min-w-0">
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
                <h3 className="text-white font-bold mb-5">Linked Department Records</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left min-w-[760px]">
                    <thead>
                      <tr className="text-zinc-500 text-[10px] uppercase border-b border-zinc-800">
                        <th className="py-3 pr-4">Source</th>
                        <th className="py-3 pr-4">Record</th>
                        <th className="py-3 pr-4">Name</th>
                        <th className="py-3 pr-4">Sector</th>
                        <th className="py-3 pr-4">Pincode</th>
                        <th className="py-3 pr-4">Link Type</th>
                        <th className="py-3 text-right">Confidence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-900">
                      {(result.linked_records || []).map((record, index) => (
                        <tr key={`${record.source}-${recordIdOf(record)}-${index}`} className="text-sm">
                          <td className="py-3 pr-4 text-zinc-200">{record.source}</td>
                          <td className="py-3 pr-4 text-zinc-400 font-mono">{recordIdOf(record)}</td>
                          <td className="py-3 pr-4 text-white">{record.name}</td>
                          <td className="py-3 pr-4 text-zinc-300">{fmt(record.sector)}</td>
                          <td className="py-3 pr-4 text-zinc-300">{fmt(record.pincode)}</td>
                          <td className="py-3 pr-4 text-zinc-400">{fmt(record.decision_type).replace(/_/g, ' ')}</td>
                          <td className="py-3 text-right text-emerald-400 font-mono">{record.confidence}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
                <h3 className="text-white font-bold mb-6">Activity Timeline</h3>
                <div className="relative border-l border-zinc-800 ml-3 space-y-8 pb-4">
                  {result.events?.map((event, index) => {
                    const style = eventStyle(event.type);
                    return (
                      <div key={index} className="relative pl-6">
                        <div className={`absolute w-3 h-3 rounded-full -left-[6.5px] top-1.5 ${style.dot}`}></div>
                        <div className="flex flex-col">
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            <span className="text-xs font-mono text-zinc-500">{event.date || 'N/A'}</span>
                            <span className="text-[10px] uppercase tracking-wider text-zinc-500">{style.label}</span>
                            {event.source && <span className="text-[10px] text-zinc-600">{event.source}</span>}
                          </div>
                          <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-lg">
                            <div className="flex items-center gap-2 mb-2">
                              {event.type === 'computed' ? <DatabaseLightningIcon size={16} className={style.icon} /> : <CheckmarkCircle01Icon size={16} className={style.icon} />}
                              <span className="text-sm font-bold text-white">{event.title}</span>
                            </div>
                            <p className="text-xs text-zinc-400">{event.desc}</p>
                            {(event.score_delta !== undefined && event.score_delta !== null) && (
                              <p className="text-[10px] text-zinc-500 mt-2">Score contribution: {Number(event.score_delta).toFixed(2)}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {(result.audit_log || []).length > 0 && (
                <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
                  <h3 className="text-white font-bold mb-5">Change History</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {result.audit_log.map((entry, index) => (
                      <div key={index} className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                        <div className="text-sm text-white font-medium">{entry.action}</div>
                        <div className="text-xs text-zinc-500 mt-1">{entry.actor} - {entry.created_at}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ActivityStatus;
