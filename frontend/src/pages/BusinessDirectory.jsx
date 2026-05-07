import { useState, useEffect, useCallback } from 'react';
import { Search01Icon } from 'hugeicons-react/icons/Search01Icon';
import { Building02Icon } from 'hugeicons-react/icons/Building02Icon';
import { FilterIcon } from 'hugeicons-react/icons/FilterIcon';
import { Download01Icon } from 'hugeicons-react/icons/Download01Icon';
import { ArrowDown01Icon } from 'hugeicons-react/icons/ArrowDown01Icon';
import { ArrowUp01Icon } from 'hugeicons-react/icons/ArrowUp01Icon';
import { ArrowRight01Icon } from 'hugeicons-react/icons/ArrowRight01Icon';
import { CheckmarkCircle01Icon } from 'hugeicons-react/icons/CheckmarkCircle01Icon';
import { Cancel01Icon } from 'hugeicons-react/icons/Cancel01Icon';
import { AlertCircleIcon } from 'hugeicons-react/icons/AlertCircleIcon';
import { api } from '../lib/api';
import { translations } from '../utils/translations';

const BusinessDirectory = ({ lang }) => {
  const t = translations[lang || 'en'];
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState({
    status: 'all',
    sector: 'all',
    hasPan: 'all',
    hasGstin: 'all'
  });
  const [sortField, setSortField] = useState('business_name');
  const [sortDirection, setSortDirection] = useState('asc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedBusiness, setSelectedBusiness] = useState(null);
  const [showFilters, setShowFilters] = useState(false);

  const fetchBusinesses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * pageSize;
      const data = await api.get('/api/business-directory', {
        params: {
          search: searchQuery,
          status: filters.status !== 'all' ? filters.status : undefined,
          sector: filters.sector !== 'all' ? filters.sector : undefined,
          has_pan: filters.hasPan !== 'all' ? filters.hasPan : undefined,
          has_gstin: filters.hasGstin !== 'all' ? filters.hasGstin : undefined,
          sort_by: sortField,
          sort_dir: sortDirection,
          limit: pageSize,
          offset
        }
      });
      setBusinesses(data.businesses || []);
      setTotalCount(data.total || 0);
    } catch (err) {
      setError('Failed to load businesses');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, filters, sortField, sortDirection, page, pageSize]);

  useEffect(() => {
    fetchBusinesses();
  }, [fetchBusinesses]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
    setPage(1);
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters({
      status: 'all',
      sector: 'all',
      hasPan: 'all',
      hasGstin: 'all'
    });
    setSearchQuery('');
    setPage(1);
  };

  const exportToCSV = () => {
    const headers = ['UBID', 'Business Name', 'Status', 'Sector', 'PAN', 'GSTIN', 'Pin Code', 'Linked Records', 'Confidence'];
    const rows = businesses.map(b => [
      b.ubid,
      b.business_name,
      b.status,
      b.sector,
      b.pan_anchor || 'N/A',
      b.gstin_anchor || 'N/A',
      b.pin_code || 'N/A',
      b.linked_record_count,
      b.confidence_score
    ]);
    
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `business-directory-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const getStatusBadge = (status) => {
    const styles = {
      Active: 'bg-emerald-500/10 text-emerald-400 border-emerald-900/30',
      Dormant: 'bg-amber-500/10 text-amber-400 border-amber-900/30',
      Closed: 'bg-rose-500/10 text-rose-400 border-rose-900/30'
    };
    return (
      <span className={`px-2 py-1 rounded border text-xs font-medium ${styles[status] || styles.Dormant}`}>
        {status}
      </span>
    );
  };

  const totalPages = Math.ceil(totalCount / pageSize);
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, totalCount);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">{t.business_directory_title}</h1>
          <p className="text-zinc-400 text-sm">{t.business_directory_subtitle}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={exportToCSV}
            disabled={businesses.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 border border-zinc-800 text-zinc-300 rounded-md text-sm font-medium transition-colors"
          >
            <Download01Icon size={16} />
            {t.export_csv}
          </button>
        </div>
      </div>

      {/* Search and Filters Bar */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-4">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search01Icon size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder={t.search_placeholder}
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
              className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-white placeholder-zinc-500 focus:border-primary focus:outline-none text-sm"
            />
          </div>

          {/* Filter Toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2 border rounded-md text-sm font-medium transition-colors ${
              showFilters ? 'bg-zinc-800 border-zinc-700 text-white' : 'bg-zinc-900 border-zinc-800 text-zinc-300 hover:bg-zinc-800'
            }`}
          >
            <FilterIcon size={16} />
            {t.filters}
            {Object.values(filters).some(v => v !== 'all') && (
              <span className="bg-primary text-zinc-950 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                {Object.values(filters).filter(v => v !== 'all').length}
              </span>
            )}
          </button>
        </div>

        {/* Expanded Filters */}
        {showFilters && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-zinc-800">
            <div>
              <label className="text-xs text-zinc-500 font-medium mb-2 block">{t.status}</label>
              <select
                value={filters.status}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-sm text-white focus:border-primary focus:outline-none"
              >
                <option value="all">{t.all_statuses}</option>
                <option value="Active">{t.active}</option>
                <option value="Dormant">{t.dormant}</option>
                <option value="Closed">{t.closed}</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-500 font-medium mb-2 block">{t.sector}</label>
              <select
                value={filters.sector}
                onChange={(e) => handleFilterChange('sector', e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-sm text-white focus:border-primary focus:outline-none"
              >
                <option value="all">{t.all_sectors}</option>
                <option value="Engineering">Engineering</option>
                <option value="Electronics/IT">Electronics/IT</option>
                <option value="Chemicals & Pharma">Chemicals & Pharma</option>
                <option value="Services">Services</option>
                <option value="Others">Others</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-500 font-medium mb-2 block">{t.has_pan}</label>
              <select
                value={filters.hasPan}
                onChange={(e) => handleFilterChange('hasPan', e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-sm text-white focus:border-primary focus:outline-none"
              >
                <option value="all">{t.any_identifier}</option>
                <option value="true">{t.yes}</option>
                <option value="false">{t.no}</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-500 font-medium mb-2 block">{t.has_gstin}</label>
              <select
                value={filters.hasGstin}
                onChange={(e) => handleFilterChange('hasGstin', e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-sm text-white focus:border-primary focus:outline-none"
              >
                <option value="all">{t.any_identifier}</option>
                <option value="true">{t.yes}</option>
                <option value="false">{t.no}</option>
              </select>
            </div>
          </div>
        )}

        {/* Active Filters Display */}
        {(Object.values(filters).some(v => v !== 'all') || searchQuery) && (
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <span className="text-xs text-zinc-500">{t.filters}:</span>
            {searchQuery && (
              <span className="text-xs bg-zinc-800 text-zinc-300 px-2 py-1 rounded flex items-center gap-1">
                Search: {searchQuery}
                <button onClick={() => setSearchQuery('')} className="hover:text-white"><Cancel01Icon size={12} /></button>
              </span>
            )}
            {Object.entries(filters).map(([key, value]) => value !== 'all' && (
              <span key={key} className="text-xs bg-zinc-800 text-zinc-300 px-2 py-1 rounded flex items-center gap-1 capitalize">
                {key.replace(/([A-Z])/g, ' $1').trim()}: {value}
                <button onClick={() => handleFilterChange(key, 'all')} className="hover:text-white"><Cancel01Icon size={12} /></button>
              </span>
            ))}
            <button
              onClick={clearFilters}
              className="text-xs text-primary hover:text-primary/80 underline ml-2"
            >
              {t.clear || 'Clear all'}
            </button>
          </div>
        )}
      </div>

      {/* Results Count */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-zinc-400">
          {t.showing_results.replace('{start}', totalCount > 0 ? startItem : 0).replace('{end}', endItem).replace('{total}', totalCount)}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-zinc-400 text-xs">{t.page_size}:</span>
          <select
            value={pageSize}
            onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
            className="px-2 py-1 bg-zinc-900 border border-zinc-800 rounded text-sm text-white focus:border-primary focus:outline-none"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center">
            <div className="w-8 h-8 border-2 border-zinc-700 border-t-primary rounded-full animate-spin mb-4" />
            <p className="text-zinc-400">{t.loading}...</p>
          </div>
        ) : error ? (
          <div className="p-16 flex flex-col items-center justify-center text-center">
            <AlertCircleIcon size={48} className="text-rose-500 mb-4" />
            <p className="text-zinc-300 mb-2">{error}</p>
            <button
              onClick={fetchBusinesses}
              className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 rounded-md text-sm font-medium"
            >
              {t.retry}
            </button>
          </div>
        ) : businesses.length === 0 ? (
          <div className="p-16 flex flex-col items-center justify-center text-center">
            <Building02Icon size={48} className="text-zinc-600 mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">{t.no_businesses_found}</h3>
            <p className="text-zinc-400 text-sm">{t.try_adjusting}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-900 text-zinc-400 border-b border-zinc-800">
                <tr>
                  <th className="px-4 py-3 font-medium">
                    <button
                      onClick={() => handleSort('business_name')}
                      className="flex items-center gap-1 hover:text-white"
                    >
                      {t.business_name}
                      {sortField === 'business_name' && (
                        sortDirection === 'asc' ? <ArrowUp01Icon size={14} /> : <ArrowDown01Icon size={14} />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-3 font-medium">UBID</th>
                  <th className="px-4 py-3 font-medium">
                    <button
                      onClick={() => handleSort('status')}
                      className="flex items-center gap-1 hover:text-white"
                    >
                      {t.status}
                      {sortField === 'status' && (
                        sortDirection === 'asc' ? <ArrowUp01Icon size={14} /> : <ArrowDown01Icon size={14} />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-3 font-medium">{t.sector}</th>
                  <th className="px-4 py-3 font-medium">{t.pan}</th>
                  <th className="px-4 py-3 font-medium">{t.linked_records}</th>
                  <th className="px-4 py-3 font-medium">{t.confidence}</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {businesses.map((business) => (
                  <tr
                    key={business.ubid}
                    className="hover:bg-zinc-900/30 transition-colors cursor-pointer"
                    onClick={() => setSelectedBusiness(business)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center">
                          <Building02Icon size={16} className="text-zinc-500" />
                        </div>
                        <div>
                          <p className="font-medium text-white">{business.business_name}</p>
                          <p className="text-xs text-zinc-500">{business.pin_code || t.no_data}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-zinc-400">{business.ubid}</span>
                    </td>
                    <td className="px-4 py-3">{getStatusBadge(business.status)}</td>
                    <td className="px-4 py-3 text-zinc-300">{business.sector || t.unknown}</td>
                    <td className="px-4 py-3">
                      <span className={`font-mono text-xs ${business.pan_anchor ? 'text-emerald-400' : 'text-zinc-500'}`}>
                        {business.pan_anchor || 'N/A'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-zinc-300">{business.linked_record_count || 0}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full"
                            style={{ width: `${(business.confidence_score || 0) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-zinc-400">
                          {Math.round((business.confidence_score || 0) * 100)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <ArrowRight01Icon size={16} className="text-zinc-600" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {!loading && businesses.length > 0 && (
        <div className="flex items-center justify-between">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed border border-zinc-800 text-zinc-300 rounded-md text-sm font-medium"
          >
            {t.previous}
          </button>
          <div className="flex items-center gap-2">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const pageNum = i + 1;
              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`w-8 h-8 rounded-md text-sm font-medium ${
                    page === pageNum
                      ? 'bg-primary text-zinc-950'
                      : 'bg-zinc-900 text-zinc-300 hover:bg-zinc-800'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
            {totalPages > 5 && <span className="text-zinc-500">...</span>}
          </div>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed border border-zinc-800 text-zinc-300 rounded-md text-sm font-medium"
          >
            {t.next}
          </button>
        </div>
      )}

      {/* Business Detail Modal */}
      {selectedBusiness && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6 border-b border-zinc-800">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center">
                    <Building02Icon size={24} className="text-primary" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">{selectedBusiness.business_name}</h2>
                    <p className="text-sm text-zinc-400 font-mono">{selectedBusiness.ubid}</p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedBusiness(null)}
                  className="p-2 hover:bg-zinc-900 rounded-lg text-zinc-400 hover:text-white"
                >
                  <Cancel01Icon size={20} />
                </button>
              </div>
            </div>
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Status</p>
                  {getStatusBadge(selectedBusiness.status)}
                </div>
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Sector</p>
                  <p className="text-white font-medium">{selectedBusiness.sector || 'Unknown'}</p>
                </div>
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">PAN</p>
                  <p className="text-white font-mono text-sm">{selectedBusiness.pan_anchor || 'Not available'}</p>
                </div>
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">GSTIN</p>
                  <p className="text-white font-mono text-sm">{selectedBusiness.gstin_anchor || 'Not available'}</p>
                </div>
              </div>
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Match Confidence</p>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full"
                      style={{ width: `${(selectedBusiness.confidence_score || 0) * 100}%` }}
                    />
                  </div>
                  <span className="text-white font-medium">{Math.round((selectedBusiness.confidence_score || 0) * 100)}%</span>
                </div>
              </div>
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Linked Records</p>
                <p className="text-2xl font-bold text-white">{selectedBusiness.linked_record_count || 0}</p>
                <p className="text-xs text-zinc-400 mt-1">Source records from different departments</p>
              </div>
            </div>
            <div className="p-6 border-t border-zinc-800 flex gap-3">
              <button
                onClick={() => window.location.href = `/entity-linker?ubid=${selectedBusiness.ubid}`}
                className="flex-1 px-4 py-2 bg-primary hover:bg-primary/90 text-zinc-950 rounded-md text-sm font-medium transition-colors"
              >
                View Details
              </button>
              <button
                onClick={() => setSelectedBusiness(null)}
                className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 rounded-md text-sm font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BusinessDirectory;
