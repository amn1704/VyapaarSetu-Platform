import { useEffect, useState } from 'react';
import { CheckmarkCircle01Icon } from 'hugeicons-react/icons/CheckmarkCircle01Icon';
import { PlayIcon } from 'hugeicons-react/icons/PlayIcon';
import { ComputerTerminal01Icon } from 'hugeicons-react/icons/ComputerTerminal01Icon';
import { ArrowRight01Icon } from 'hugeicons-react/icons/ArrowRight01Icon';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { translations } from '../utils/translations';

const friendlyColumnNames = {
  ubid: 'Business ID',
  business_name: 'Business Name',
  status: 'Status',
  sector: 'Business Type',
  pin_code: 'PIN Code',
  pan_anchor: 'PAN',
  gstin_anchor: 'GSTIN',
  confidence_score: 'Match Confidence',
  last_inspection_date: 'Last Inspection',
  ubid_count: 'Businesses',
  avg_link_confidence: 'Average Match Confidence',
  average_match_confidence: 'Average Match Confidence',
  business_count: 'Businesses',
  active_count: 'Active',
  dormant_count: 'Dormant',
  closed_count: 'Closed',
  record_count: 'Records',
  linked_business_count: 'Linked Businesses',
  source_system: 'Department',
  priority: 'Priority',
  queued_at: 'Added On'
};

const friendlyColumnName = (key) => (
  friendlyColumnNames[key] || key.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase())
);

const displayValue = (value) => {
  if (value === null || value === undefined || value === '') return 'N/A';
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(3);
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const ResultsTable = ({ rows, title, countLabel, onOpen }) => (
  <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 md:p-6 min-w-0">
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
      <h3 className="text-lg font-bold text-white flex items-center gap-2">
        <CheckmarkCircle01Icon className="text-emerald-500" size={20} />
        {title}
      </h3>
      <span className="text-sm font-mono text-zinc-500">{rows.length} {countLabel || 'records'}</span>
    </div>

    {rows.length > 0 ? (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left">
          <thead>
            <tr className="text-zinc-500 text-xs uppercase border-b border-zinc-800">
              {Object.keys(rows[0]).map(k => (
                <th key={k} className="p-3 font-medium">{friendlyColumnName(k)}</th>
              ))}
              {rows[0].ubid && <th className="p-3 font-medium text-right">Open</th>}
            </tr>
          </thead>
          <tbody className="text-sm">
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-zinc-900 hover:bg-zinc-900/50 transition-colors">
                {Object.values(row).map((val, j) => (
                  <td key={j} className="p-3 text-zinc-300">{displayValue(val)}</td>
                ))}
                {row.ubid && (
                  <td className="p-3 text-right">
                    <button
                      onClick={() => onOpen(row.ubid)}
                      className="text-primary hover:text-primary/80 transition-colors"
                    >
                      <ArrowRight01Icon size={18} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : (
      <div className="text-center py-12 text-zinc-500">No exact rows matched this query.</div>
    )}
  </div>
);

const QueryEngine = ({ lang }) => {
  const t = translations[lang || 'en'];
  const [searchParams] = useSearchParams();
  const urlQuestion = searchParams.get('q');
  const [query, setQuery] = useState(t.query_placeholder);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [message, setMessage] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (urlQuestion) setQuery(urlQuestion);
  }, [urlQuestion]);

  const handleRunQuery = async () => {
    setIsRunning(true);
    setResults(null);
    setMessage(null);

    try {
      const data = await api.post('/api/query', { question: query });
      setResults(data);
      setIsRunning(false);
      if (data.answer_mode === 'no_exact_match_with_related') {
        setMessage(`No exact matches. Showing ${data.related_row_count || 0} related rows to help refine the question.`);
      } else {
        setMessage(`Answer ready. (${data.row_count ?? (data.results || []).length} records found)`);
      }
    } catch (err) {
      console.error('Query failed', err);
      setResults({ results: [], summary_report: err.message || 'Query failed.' });
      setMessage(err.message || 'Query failed.');
      setIsRunning(false);
    }
  };

  const handleUBIDClick = (ubid) => {
    navigate(`/activity-status?ubid=${encodeURIComponent(ubid)}`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white mb-1">{t.query_engine_title}</h1>
        <p className="text-zinc-400 text-sm">
          {t.query_engine_subtitle}
        </p>
      </div>

      <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-1 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-rose-500"></div>
            <div className="w-3 h-3 rounded-full bg-amber-500"></div>
            <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
            <span className="text-xs text-zinc-500 ml-2">{t.local_question_helper}</span>
          </div>
          <span className="text-[10px] text-zinc-500 font-mono">READ ONLY</span>
        </div>

        <div className="p-6">
          <div className="relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-4 pl-12 text-zinc-100 font-mono text-sm focus:outline-none focus:border-primary resize-none h-24"
              placeholder={t.query_placeholder}
            />
            <ComputerTerminal01Icon className="absolute left-4 top-4 text-zinc-500" size={20} />
          </div>

          <div className="mt-4 flex justify-end">
            <button
              onClick={handleRunQuery}
              disabled={isRunning || !query}
              className="flex items-center gap-2 px-6 py-2 bg-primary hover:bg-primary/90 disabled:bg-primary/50 text-white rounded-md font-medium transition-all"
            >
              {isRunning ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              ) : (
                <PlayIcon size={16} />
              )}
              {isRunning ? t.loading : t.get_answer}
            </button>
          </div>
        </div>
      </div>

      {message && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm text-zinc-300">
          {message}
        </div>
      )}

      {results !== null && (
        <div className="space-y-6 animate-in slide-in-from-bottom-4 fade-in">
          <div className="bg-sky-500/5 border border-sky-500/10 rounded-xl p-6">
            <h4 className="text-sky-400 text-xs font-bold uppercase tracking-widest mb-3">{t.summary_report}</h4>
            <div className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
              {results.summary_report}
            </div>
          </div>

          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-0 overflow-hidden">
            <div className="bg-zinc-900 px-4 py-2 border-b border-zinc-800 flex justify-between items-center">
              <span className="text-[10px] font-mono text-zinc-500">{t.generated_sql}</span>
              <span className="text-[9px] px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded">SAFE</span>
            </div>
            <div className="p-4 bg-zinc-950 font-mono text-xs text-zinc-400 overflow-x-auto">
              {results.generated_sql}
            </div>
          </div>

          <ResultsTable
            rows={results.results || []}
            title={t.results}
            countLabel={t.rows}
            onOpen={handleUBIDClick}
          />

          {(results.related_results || []).length > 0 && (
            <>
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-0 overflow-hidden">
                <div className="bg-zinc-900 px-4 py-2 border-b border-zinc-800 flex justify-between items-center">
                  <span className="text-[10px] font-mono text-zinc-500">{t.query_placeholder}</span>
                  <span className="text-[9px] px-2 py-0.5 bg-amber-500/10 text-amber-300 rounded">RELAXED</span>
                </div>
                <div className="p-4 bg-zinc-950 font-mono text-xs text-zinc-400 overflow-x-auto">
                  {results.related_sql}
                </div>
              </div>

              <ResultsTable
                rows={results.related_results || []}
                title={results.related_title || t.results}
                countLabel={t.rows}
                onOpen={handleUBIDClick}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default QueryEngine;
