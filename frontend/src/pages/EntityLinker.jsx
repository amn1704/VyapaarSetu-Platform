import { useState } from 'react';
import { AiSearchIcon } from 'hugeicons-react/icons/AiSearchIcon';
import { FolderShared01Icon } from 'hugeicons-react/icons/FolderShared01Icon';
import { CancelCircleIcon } from 'hugeicons-react/icons/CancelCircleIcon';
import { CopyLinkIcon } from 'hugeicons-react/icons/CopyLinkIcon';
import { DocumentCodeIcon } from 'hugeicons-react/icons/DocumentCodeIcon';
import { Loading01Icon } from 'hugeicons-react/icons/Loading01Icon';
import { Activity01Icon } from 'hugeicons-react/icons/Activity01Icon';
import { Alert02Icon } from 'hugeicons-react/icons/Alert02Icon';
import { CheckmarkCircle01Icon } from 'hugeicons-react/icons/CheckmarkCircle01Icon';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';

const examples = ['TAX-Q49', 'MUC-Q49', 'TAX-49311', '560058', 'CLASSIC ENTERPRISES'];

const recordIdOf = (record) => record?.id || record?.source_record_id || 'N/A';

const statusStyle = {
  Active: 'border-emerald-900/60 bg-emerald-950/30 text-emerald-300',
  Dormant: 'border-amber-900/60 bg-amber-950/30 text-amber-300',
  Closed: 'border-rose-900/60 bg-rose-950/30 text-rose-300',
  'Linkage Pending': 'border-amber-900/60 bg-amber-950/30 text-amber-300',
  'Not Found': 'border-rose-900/60 bg-rose-950/30 text-rose-300'
};

const EntityLinker = () => {
  const [query, setQuery] = useState('TAX-Q49');
  const [isSearching, setIsSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const navigate = useNavigate();

  const handleSearch = (e, overrideQuery) => {
    if (e) e.preventDefault();
    const searchValue = (overrideQuery || query).trim();
    if (!searchValue) return;

    setQuery(searchValue);
    setIsSearching(true);
    setHasSearched(true);
    setError(null);
    setResult(null);

    api.get('/api/entity/lookup', { params: { query: searchValue } })
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

  const isCanonical = result?.trace_status === 'canonical_ubid_found';
  const isPending = result?.trace_status === 'review_confirmed_linkage_pending' || result?.trace_status === 'raw_record_unlinked';

  return (
    <div className="space-y-6">
      <div className="flex flex-col mb-2">
        <h1 className="text-2xl font-bold text-white mb-1">Find a Business</h1>
        <p className="text-zinc-400 text-sm">
          Search by department record ID, PAN, GSTIN, business name, address, or PIN code.
        </p>
      </div>

      <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6 shadow-sm">
        <form onSubmit={handleSearch} className="flex flex-col gap-4">
          <div className="flex flex-col lg:flex-row gap-4">
            <div className="relative flex-1">
              <AiSearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={18} />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Try TAX-Q49, MUC-Q49, a business name, or PIN code"
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg py-3 pl-10 pr-4 text-sm text-zinc-100 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all placeholder:text-zinc-600"
              />
            </div>
            <button
              type="submit"
              disabled={isSearching}
              className="flex items-center justify-center gap-2 px-6 py-3 bg-primary hover:bg-primary/90 disabled:bg-primary/50 text-white rounded-lg font-medium transition-colors shadow-sm whitespace-nowrap lg:w-auto"
            >
              {isSearching ? <Loading01Icon size={16} className="animate-spin" /> : <FolderShared01Icon size={16} />}
              Find Business
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {examples.map(item => (
              <button
                key={item}
                type="button"
                onClick={(e) => handleSearch(e, item)}
                className="px-3 py-1.5 rounded-md border border-zinc-800 bg-zinc-900/70 text-xs text-zinc-400 hover:text-white hover:border-primary transition-colors"
              >
                {item}
              </button>
            ))}
          </div>
        </form>
      </div>

      {isSearching && (
        <div className="flex flex-col items-center justify-center p-12 text-zinc-500">
          <Loading01Icon size={32} className="animate-spin mb-4 text-primary" />
          <p>Searching department records and business links...</p>
        </div>
      )}

      {error && !isSearching && (
        <EmptyState title="Search Failed" message={error} />
      )}

      {hasSearched && !isSearching && result && !result.found && (
        <EmptyState
          title="No Business Found"
          message="No raw or canonical record matched this input. Try a department ID, PAN, GSTIN, business name, address or pincode."
        />
      )}

      {hasSearched && !isSearching && result?.found && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
          <div className={`border rounded-xl p-5 overflow-hidden ${isCanonical ? 'border-emerald-900/60 bg-emerald-950/10' : 'border-amber-900/60 bg-amber-950/10'}`}>
            <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(460px,580px)] gap-5 items-center">
              <div className="min-w-0">
                <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-md border text-xs font-bold mb-3 ${statusStyle[result.status] || statusStyle['Linkage Pending']}`}>
                  {isCanonical ? <CheckmarkCircle01Icon size={14} /> : <Alert02Icon size={14} />}
                  {isCanonical ? 'Business ID found' : result.trace_status === 'review_confirmed_linkage_pending' ? 'Officer confirmed this match; business ID is pending' : 'Department record found; match still pending'}
                </div>
                <h2 className="text-2xl md:text-3xl font-bold text-white font-mono break-words">{result.ubid || 'Business ID not assigned yet'}</h2>
                <p className="text-zinc-300 mt-1">{result.canonical_name || 'Unknown Business'}</p>
              </div>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 min-w-0">
                <TraceStat label="Record Matches" value={result.summary?.raw_matches || 0} />
                <TraceStat label="Linked Records" value={result.summary?.linked_records || 0} />
                <TraceStat label="Possible Matches" value={result.summary?.candidate_pairs || 0} />
                <TraceStat label="Departments" value={result.summary?.departments || 0} />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)] gap-6">
            <div className="space-y-6 min-w-0">
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden">
                <SectionHeader icon={<CopyLinkIcon size={16} />} title={`Department Records (${result.raw_records?.length || 0})`} />
                <div className="divide-y divide-zinc-800/50 max-h-[520px] overflow-y-auto">
                  {(result.raw_records || []).map((record, idx) => (
                    <RawRecordCard key={`${record.source}-${recordIdOf(record)}-${idx}`} record={record} searched={result.searched_query} />
                  ))}
                </div>
              </div>

              {isCanonical && (
                <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5">
                  <SectionTitle icon={<Activity01Icon size={16} />} title="Business Status" />
                  <div className={`inline-flex mt-4 px-3 py-1.5 rounded-md border text-sm font-bold ${statusStyle[result.status] || 'border-zinc-800 bg-zinc-900 text-zinc-300'}`}>
                    {result.status}
                  </div>
                  <p className="text-xs text-zinc-500 mt-3">
                    Score: {Number(result.activity_score || 0).toFixed(2)} - Computed: {result.activity_computed_at || 'N/A'}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-6 min-w-0">
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6 min-w-0 overflow-hidden">
                <SectionTitle icon={<DocumentCodeIcon size={18} />} title="How Records Connect" />
                <EvidenceGraph result={result} />
              </div>

              {isCanonical && (
                <LinkedRecordsTable records={result.linked_records || []} navigate={navigate} ubid={result.ubid} />
              )}

              {isPending && (
                <CandidatePairs pairs={result.candidate_pairs || []} />
              )}

              {(result.recommendations || []).length > 0 && (
                <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5">
                  <SectionTitle icon={<Alert02Icon size={16} />} title="Suggested Next Steps" />
                  <div className="space-y-2 mt-4">
                    {result.recommendations.map((item, idx) => (
                      <p key={idx} className="text-sm text-zinc-300 bg-zinc-900/60 border border-zinc-800 rounded-lg p-3">{item}</p>
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

const EmptyState = ({ title, message }) => (
  <div className="bg-red-950/20 border border-red-900/50 rounded-xl p-8 flex flex-col items-center justify-center text-center animate-in fade-in slide-in-from-top-4">
    <div className="w-12 h-12 bg-red-900/30 rounded-full flex items-center justify-center mb-4">
      <CancelCircleIcon className="text-red-500" size={24} />
    </div>
    <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
    <p className="text-zinc-400 max-w-xl mx-auto">{message}</p>
  </div>
);

const TraceStat = ({ label, value }) => (
  <div className="bg-zinc-950/70 border border-zinc-800 rounded-lg p-3 min-w-0">
    <p className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</p>
    <p className="text-xl font-bold text-white truncate">{Number(value || 0).toLocaleString()}</p>
  </div>
);

const SectionHeader = ({ icon, title }) => (
  <div className="p-4 border-b border-zinc-800 flex items-center gap-2">
    <span className="text-zinc-400">{icon}</span>
    <h3 className="text-sm font-bold text-white">{title}</h3>
  </div>
);

const SectionTitle = ({ icon, title }) => (
  <h3 className="text-base font-bold text-white flex items-center gap-2">
    <span className="text-accent">{icon}</span>
    {title}
  </h3>
);

const RawRecordCard = ({ record, searched }) => {
  const recordId = recordIdOf(record);
  const isHit = recordId?.toUpperCase() === searched?.toUpperCase();
  return (
    <div className={`p-4 ${isHit ? 'bg-primary/5' : ''}`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="text-xs font-medium text-zinc-500 uppercase">{record.source}</div>
          <div className="text-sm font-mono font-bold text-zinc-100">{recordId}</div>
        </div>
        {record.linked_ubid ? (
          <span className="text-[10px] px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-900/50">Linked</span>
        ) : (
          <span className="text-[10px] px-2 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-900/50">Unlinked</span>
        )}
      </div>
      <p className="text-sm font-semibold text-white">{record.name}</p>
      <p className="text-xs text-zinc-500 mt-1">{record.address || 'Address unavailable'}</p>
      <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
        <MiniField label="PAN" value={record.pan || 'N/A'} good={record.pan_valid} />
        <MiniField label="GSTIN" value={record.gstin || 'N/A'} good={record.gstin_valid} />
        <MiniField label="Pincode" value={record.pincode || 'N/A'} />
        <MiniField label="Sector" value={record.sector || 'Unknown'} />
      </div>
    </div>
  );
};

const MiniField = ({ label, value, good }) => (
  <div className="bg-zinc-900/70 border border-zinc-800 rounded-md p-2">
    <p className="text-[10px] text-zinc-500 uppercase">{label}</p>
    <p className={`font-mono text-[11px] mt-0.5 ${good ? 'text-emerald-300' : 'text-zinc-300'}`}>{value}</p>
  </div>
);

const EvidenceGraph = ({ result }) => {
  const records = result.linked_records?.length ? result.linked_records : result.raw_records || [];
  return (
    <div className="mt-5 bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4 md:p-6 overflow-x-auto">
      <div className="min-w-[640px] flex items-center justify-center gap-10">
        <div className="space-y-3">
          {records.slice(0, 6).map((record, idx) => (
            <div key={`${recordIdOf(record)}-${idx}`} className="relative px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-md">
              <p className="text-[10px] text-zinc-500 uppercase">{record.source}</p>
              <p className="text-xs font-mono text-zinc-200">{recordIdOf(record)}</p>
              <div className="absolute top-1/2 -right-10 w-10 h-px bg-zinc-700"></div>
            </div>
          ))}
        </div>
        <div className={`px-6 py-4 rounded-xl border ${result.ubid ? 'bg-emerald-950/30 border-emerald-500/40' : 'bg-amber-950/30 border-amber-500/40'}`}>
          <p className={`text-[10px] font-bold uppercase tracking-wider ${result.ubid ? 'text-emerald-400' : 'text-amber-400'}`}>
            {result.ubid ? 'Business ID' : 'Match Decision'}
          </p>
          <p className="text-base md:text-lg font-mono font-bold text-white mt-1 break-words">{result.ubid || 'Business ID pending'}</p>
          <p className="text-xs text-zinc-400 mt-1">{result.canonical_name}</p>
        </div>
      </div>
    </div>
  );
};

const LinkedRecordsTable = ({ records, navigate, ubid }) => (
  <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden">
    <SectionHeader icon={<CopyLinkIcon size={16} />} title={`Linked Department Records (${records.length})`} />
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="text-zinc-500 text-xs uppercase border-b border-zinc-800">
            <th className="p-3">Department</th>
            <th className="p-3">Record ID</th>
            <th className="p-3">Business Name</th>
            <th className="p-3">PAN</th>
            <th className="p-3">Pincode</th>
            <th className="p-3">Confidence</th>
          </tr>
        </thead>
        <tbody className="text-sm">
          {records.map((record, idx) => (
            <tr key={`${recordIdOf(record)}-${idx}`} className="border-b border-zinc-900 hover:bg-zinc-900/50 transition-colors cursor-pointer" onClick={() => navigate(`/activity-status?ubid=${encodeURIComponent(ubid)}`)}>
              <td className="p-3 text-zinc-400">{record.source}</td>
              <td className="p-3 text-zinc-200 font-mono">{recordIdOf(record)}</td>
              <td className="p-3 text-zinc-300">{record.name}</td>
              <td className="p-3 text-zinc-300 font-mono">{record.pan || 'N/A'}</td>
              <td className="p-3 text-zinc-300">{record.pincode || 'N/A'}</td>
              <td className="p-3 text-emerald-400 font-bold">{record.match_confidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

const CandidatePairs = ({ pairs }) => (
  <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden">
    <SectionHeader icon={<DocumentCodeIcon size={16} />} title={`Possible Match Evidence (${pairs.length})`} />
    <div className="divide-y divide-zinc-800/50">
      {pairs.length === 0 && <p className="p-5 text-sm text-zinc-500">No possible match evidence is available for this department record yet.</p>}
      {pairs.map(pair => (
        <div key={pair.pair_id} className="p-5">
          <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4 mb-4">
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-wider">{pair.blocking_strategy}</p>
              <p className="text-sm text-white mt-1">{pair.recordA?.id} <span className="text-zinc-600">&lt;-&gt;</span> {pair.recordB?.id}</p>
            </div>
            <div className="lg:text-right">
              <p className="text-xs text-zinc-500">Confidence</p>
              <p className="text-xl font-bold text-amber-400">{pair.confidence}%</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <PairRecord record={pair.recordA} />
            <PairRecord record={pair.recordB} />
          </div>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-3">
              <p className="text-xs text-zinc-500 uppercase mb-2">Evidence</p>
              {Object.entries(pair.evidence || {}).map(([key, value]) => (
                <p key={key} className="text-xs text-zinc-300">{key.replace(/_/g, ' ')}: <span className="text-white">{String(value)}</span></p>
              ))}
            </div>
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-3">
              <p className="text-xs text-zinc-500 uppercase mb-2">Reviewer Decision</p>
              <p className="text-sm text-white">{pair.review?.decision || pair.review?.status || 'Not queued'}</p>
              <p className="text-xs text-zinc-500 mt-1">By {pair.review?.reviewer_id || 'N/A'} on {pair.review?.reviewed_at || 'N/A'}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
);

const PairRecord = ({ record }) => (
  <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-3">
    <p className="text-xs text-zinc-500 uppercase">{record?.source}</p>
    <p className="text-sm font-mono text-white mt-1">{record?.id}</p>
    <p className="text-xs text-zinc-400 mt-1">{record?.name}</p>
    <p className="text-xs text-zinc-500 mt-2">PAN: <span className="text-zinc-300 font-mono">{record?.pan || 'N/A'}</span></p>
  </div>
);

export default EntityLinker;
