import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft01Icon } from 'hugeicons-react/icons/ArrowLeft01Icon';
import { ArrowRight01Icon } from 'hugeicons-react/icons/ArrowRight01Icon';
import { AiSearchIcon } from 'hugeicons-react/icons/AiSearchIcon';
import { api } from '../lib/api';

const PAGE_SIZE = 50;

const titleCase = (value) => String(value || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

const staticIdentifierOptions = [
  { label: 'Any Identifier', value: 'all' },
  { label: 'Has PAN', value: 'pan' },
  { label: 'Has GSTIN', value: 'gstin' },
  { label: 'Missing PAN', value: 'missing_pan' },
  { label: 'Missing GSTIN', value: 'missing_gstin' }
];

const linkedOptions = [
  { label: 'All Link States', value: 'all' },
  { label: 'Linked to Business ID', value: 'linked' },
  { label: 'Not Linked Yet', value: 'unlinked' }
];

const sortOptions = [
  { label: 'Newest First', value: 'newest' },
  { label: 'Oldest First', value: 'oldest' },
  { label: 'Highest Match Confidence', value: 'confidence' },
  { label: 'Business Name', value: 'name' }
];

const RawRecords = () => {
  const [filters, setFilters] = useState({
    source: 'all',
    sector: 'all',
    status: 'all',
    linked: 'all',
    identifier: 'all',
    pincode: 'all',
    sort: 'newest',
    q: ''
  });
  const [records, setRecords] = useState([]);
  const [facets, setFacets] = useState({ sources: [], sectors: [], statuses: [], pincodes: [] });
  const [summary, setSummary] = useState({ linked: 0, unlinked: 0, with_pan: 0, with_gstin: 0, avg_confidence: 0 });
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);

  const setFilter = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(0);
  };

  const fetchPage = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        sort: filters.sort
      };
      Object.entries(filters).forEach(([key, value]) => {
        if (value && value !== 'all' && key !== 'sort') params[key] = value;
      });
      const data = await api.get('/api/raw-records', { params });
      setRecords(data.records || []);
      setFacets(data.facets || { sources: [], sectors: [], statuses: [], pincodes: [] });
      setSummary(data.summary || {});
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to fetch raw records', err);
      setRecords([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    fetchPage();
  }, [fetchPage]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const activeFilterCount = useMemo(
    () => Object.entries(filters).filter(([key, value]) => key !== 'sort' && value && value !== 'all').length,
    [filters]
  );

  const resetFilters = () => {
    setFilters({ source: 'all', sector: 'all', status: 'all', linked: 'all', identifier: 'all', pincode: 'all', sort: 'newest', q: '' });
    setPage(0);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 mb-2">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Department Records</h1>
          <p className="text-zinc-400 text-sm">
            Search, filter, and inspect source records before they become a trusted business identity.{' '}
            <span className="text-zinc-500 font-mono">{total.toLocaleString()} matching records</span>
          </p>
        </div>
        <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 flex flex-col lg:flex-row gap-3 lg:items-center">
          <div className="relative flex-1 min-w-0">
            <AiSearchIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              value={filters.q}
              onChange={(e) => setFilter('q', e.target.value)}
              placeholder="Search ID, name, PAN, GSTIN, address..."
              className="bg-zinc-900 border border-zinc-800 text-sm text-zinc-300 rounded-md pl-8 pr-3 py-2.5 outline-none focus:border-primary w-full"
            />
          </div>
          <button
            onClick={resetFilters}
            className="px-4 py-2.5 rounded-md bg-zinc-900 border border-zinc-800 text-sm text-zinc-300 hover:text-white whitespace-nowrap"
          >
            Clear filters{activeFilterCount ? ` (${activeFilterCount})` : ''}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard label="Linked" value={summary.linked} tone="success" />
        <SummaryCard label="Not Linked" value={summary.unlinked} tone="warning" />
        <SummaryCard label="With PAN" value={summary.with_pan} />
        <SummaryCard label="Avg Match" value={`${summary.avg_confidence || 0}%`} />
      </div>

      <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 overflow-hidden">
        <div className="grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-3">
          <FilterSelect label="Department" value={filters.source} onChange={v => setFilter('source', v)} options={[{ label: 'All Departments', value: 'all' }, ...facets.sources.map(item => ({ label: `${titleCase(item.name)} (${item.value})`, value: item.name }))]} />
          <FilterSelect label="Business Type" value={filters.sector} onChange={v => setFilter('sector', v)} options={[{ label: 'All Types', value: 'all' }, ...facets.sectors.map(item => ({ label: `${item.name} (${item.value})`, value: item.name }))]} />
          <FilterSelect label="Status" value={filters.status} onChange={v => setFilter('status', v)} options={[{ label: 'All Statuses', value: 'all' }, ...facets.statuses.map(item => ({ label: `${item.name} (${item.value})`, value: item.name }))]} />
          <FilterSelect label="Link State" value={filters.linked} onChange={v => setFilter('linked', v)} options={linkedOptions} />
          <FilterSelect label="Identifier" value={filters.identifier} onChange={v => setFilter('identifier', v)} options={staticIdentifierOptions} />
          <FilterSelect label="PIN Code" value={filters.pincode} onChange={v => setFilter('pincode', v)} options={[{ label: 'All PIN Codes', value: 'all' }, ...facets.pincodes.map(item => ({ label: `${item.name} (${item.value})`, value: item.name }))]} />
          <FilterSelect label="Sort" value={filters.sort} onChange={v => setFilter('sort', v)} options={sortOptions} />
        </div>
      </div>

      <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden min-w-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-zinc-400 min-w-[1200px]">
            <thead className="text-xs uppercase bg-zinc-900/50 text-zinc-500 border-b border-zinc-800">
              <tr>
                <th className="px-5 py-4">Source ID</th>
                <th className="px-5 py-4">Department</th>
                <th className="px-5 py-4">Business Name</th>
                <th className="px-5 py-4">Type</th>
                <th className="px-5 py-4">PIN</th>
                <th className="px-5 py-4">Status</th>
                <th className="px-5 py-4">PAN</th>
                <th className="px-5 py-4">GSTIN</th>
                <th className="px-5 py-4">Business ID</th>
                <th className="px-5 py-4 text-right">Match</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center">
                    <div className="flex items-center justify-center gap-3 text-zinc-500">
                      <div className="w-5 h-5 border-2 border-zinc-700 border-t-primary rounded-full animate-spin" />
                      Loading records...
                    </div>
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-zinc-500">No records match the selected filters.</td>
                </tr>
              ) : (
                records.map((record, i) => (
                  <tr key={`${record.source}-${record.id}-${i}`} className="border-b border-zinc-800 hover:bg-zinc-900/30 transition-colors">
                    <td className="px-5 py-4 font-mono text-zinc-300">{record.id}</td>
                    <td className="px-5 py-4"><Badge>{titleCase(record.source)}</Badge></td>
                    <td className="px-5 py-4 text-zinc-200">
                      <div className="font-medium">{record.name}</div>
                      <div className="text-xs text-zinc-500 truncate max-w-sm">{record.address}</div>
                    </td>
                    <td className="px-5 py-4">{record.sector}</td>
                    <td className="px-5 py-4 font-mono">{record.pincode}</td>
                    <td className="px-5 py-4"><StatusBadge status={record.status} /></td>
                    <td className="px-5 py-4 font-mono">{record.pan}</td>
                    <td className="px-5 py-4 font-mono">{record.gstin}</td>
                    <td className="px-5 py-4 font-mono text-xs text-zinc-300">{record.ubid || 'Not linked'}</td>
                    <td className="px-5 py-4 text-right text-zinc-300">{record.confidence !== null && record.confidence !== undefined ? `${record.confidence}%` : '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="px-4 md:px-6 py-4 border-t border-zinc-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-zinc-900/30">
          <span className="text-sm text-zinc-500">Page {page + 1} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed text-zinc-300 rounded-md transition-colors"
            >
              <ArrowLeft01Icon size={16} /> Prev
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1 || loading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed text-zinc-300 rounded-md transition-colors"
            >
              Next <ArrowRight01Icon size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const FilterSelect = ({ label, value, onChange, options }) => (
  <label className="space-y-1 min-w-0">
    <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold">{label}</span>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full min-w-0 bg-zinc-900 border border-zinc-800 text-sm text-zinc-300 rounded-md px-3 py-2.5 outline-none focus:border-primary truncate"
    >
      {options.map(option => (
        <option key={option.value} value={option.value}>{option.label}</option>
      ))}
    </select>
  </label>
);

const SummaryCard = ({ label, value, tone = 'neutral' }) => {
  const color = tone === 'success' ? 'text-emerald-400' : tone === 'warning' ? 'text-amber-400' : 'text-white';
  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4">
      <p className="text-xs text-zinc-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{typeof value === 'number' ? value.toLocaleString() : value}</p>
    </div>
  );
};

const Badge = ({ children }) => (
  <span className="px-2 py-1 bg-zinc-800 text-zinc-300 rounded text-xs font-medium">{children}</span>
);

const StatusBadge = ({ status }) => {
  const style = status === 'Active'
    ? 'bg-emerald-500/10 text-emerald-300 border-emerald-900/60'
    : status === 'Dormant'
      ? 'bg-amber-500/10 text-amber-300 border-amber-900/60'
      : status === 'Closed'
        ? 'bg-rose-500/10 text-rose-300 border-rose-900/60'
        : 'bg-zinc-800 text-zinc-300 border-zinc-700';
  return <span className={`px-2 py-1 rounded border text-xs font-medium ${style}`}>{status}</span>;
};

export default RawRecords;
