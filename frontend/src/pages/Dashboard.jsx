import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Activity01Icon } from 'hugeicons-react/icons/Activity01Icon';
import { Alert02Icon } from 'hugeicons-react/icons/Alert02Icon';
import { CheckmarkCircle01Icon } from 'hugeicons-react/icons/CheckmarkCircle01Icon';
import { Database01Icon } from 'hugeicons-react/icons/Database01Icon';
import { MapPinIcon } from 'hugeicons-react/icons/MapPinIcon';
import { Building02Icon } from 'hugeicons-react/icons/Building02Icon';
import { Briefcase01Icon } from 'hugeicons-react/icons/Briefcase01Icon';
import { PlayIcon } from 'hugeicons-react/icons/PlayIcon';
import { ArrowRight01Icon } from 'hugeicons-react/icons/ArrowRight01Icon';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { translations } from '../utils/translations';
import './Dashboard.css';
import { api } from '../lib/api';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

const getDataIcon = (status) => {
  let color = '#10b981';
  if (status === 'Dormant') color = '#f59e0b';
  if (status === 'Closed') color = '#ef4444';

  return L.divIcon({
    className: 'custom-data-icon',
    html: `<div class="data-dot" style="background-color: ${color};"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });
};

const COLORS = ['#1E4D8C', '#F57F17', '#10b981', '#ef4444', '#8b5cf6', '#14b8a6'];

const emptyStats = {
  metrics: {
    total_ingested: 0,
    total_ubids: 0,
    active_businesses: 0,
    pending_review: 0,
    dormant_businesses: 0,
    closed_businesses: 0,
    pan_anchored: 0,
    gstin_anchored: 0,
    linked_source_records: 0,
    pending_events: 0
  },
  charts: {
    sources: [],
    sectors: [],
    activity: [],
    pincode_hotspots: [],
    confidence_bands: [],
    source_coverage: []
  },
  query_cards: []
};

const Dashboard = ({ lang }) => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('Overview');
  const t = translations[lang || 'en'];
  const [stats, setStats] = useState(emptyStats);
  const [mapData, setMapData] = useState([]);
  const [queryRuns, setQueryRuns] = useState({});

  useEffect(() => {
    const fetchStats = () => {
      api.get('/api/dashboard')
        .then(data => setStats({ ...emptyStats, ...data, metrics: { ...emptyStats.metrics, ...(data.metrics || {}) }, charts: { ...emptyStats.charts, ...(data.charts || {}) } }))
        .catch(err => console.error('Failed to fetch dashboard stats', err));
    };

    const fetchMapData = () => {
      api.get('/api/map-data')
        .then(data => setMapData(data))
        .catch(err => console.error('Failed to fetch map data', err));
    };

    fetchStats();
    fetchMapData();
    const intervalId = setInterval(fetchStats, 2000);
    return () => clearInterval(intervalId);
  }, []);

  const runDashboardQuery = async (card) => {
    setQueryRuns(prev => ({ ...prev, [card.question]: { loading: true, data: null, error: null } }));

    try {
      const data = await api.post('/api/query', { question: card.question });
      setQueryRuns(prev => ({ ...prev, [card.question]: { loading: false, data, error: null } }));
    } catch (err) {
      setQueryRuns(prev => ({ ...prev, [card.question]: { loading: false, data: null, error: err.message } }));
    }
  };

  const openQueryEngine = (question) => {
    navigate(`/query-engine?q=${encodeURIComponent(question)}`);
  };

  const dedupeRate = stats.metrics.total_ingested > 0
    ? ((1 - stats.metrics.total_ubids / stats.metrics.total_ingested) * 100).toFixed(1)
    : '0.0';
  const queryCards = stats.query_cards.length ? stats.query_cards : [
    {
      label: 'Active industrial businesses in PIN 560058 with no inspection in the last 18 months',
      question: 'Find all active factories in pin code 560058 with no inspection in the last 18 months',
      source: 'Business register and inspection history',
      metric: 0,
      unit: 'businesses need inspection evidence',
      tone: 'primary'
    }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800 overflow-x-auto">
        <div className="flex gap-6 min-w-max">
          {[t.overview, t.geospatial, t.sectors].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab === t.overview ? 'Overview' : tab === t.geospatial ? 'Geospatial' : 'Sectors')}
              className={`text-sm font-medium pb-4 border-b-2 -mb-[17px] transition-colors ${activeTab === (tab === t.overview ? 'Overview' : tab === t.geospatial ? 'Geospatial' : 'Sectors') ? 'text-white border-primary' : 'text-zinc-400 border-transparent hover:text-zinc-200'}`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      <div>
        <h1 className="text-2xl font-bold text-white mb-1">{t.dashboard_title}</h1>
        <p className="text-zinc-400 text-sm">{t.dashboard_subtitle}</p>
      </div>

      {activeTab === 'Overview' && (
        <div className="space-y-6 animate-in fade-in">
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6">
            <MetricCard title={t.department_records} value={stats.metrics.total_ingested} note={`${stats.charts.sources.length} ${t.state_departments_connected}`} icon={<Database01Icon size={20} />} />
            <MetricCard title={t.registered_businesses} value={stats.metrics.total_ubids} note={`${dedupeRate}% ${t.duplicate_records_brought}`} icon={<Activity01Icon size={20} />} tone="primary" />
            <MetricCard title={t.currently_active} value={stats.metrics.active_businesses} note={`${stats.metrics.dormant_businesses.toLocaleString()} ${t.dormant}, ${stats.metrics.closed_businesses.toLocaleString()} ${t.closed}`} icon={<CheckmarkCircle01Icon size={20} />} tone="success" />
            <MetricCard title={t.needs_officer_review} value={stats.metrics.pending_review} note={`${stats.metrics.pending_events.toLocaleString()} ${t.events_need_matching}`} icon={<Alert02Icon size={20} />} tone="warning" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6">
            <MiniMetric title={t.businesses_with_pan} value={stats.metrics.pan_anchored} note={t.pan_available} />
            <MiniMetric title={t.businesses_with_gstin} value={stats.metrics.gstin_anchored} note={t.gstin_available} />
            <MiniMetric title={t.linked_department_records} value={stats.metrics.linked_source_records} note={t.records_matched} />
            <MiniMetric title={t.duplicate_reduction} value={`${dedupeRate}%`} note={t.repeated_records_together} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6 shadow-sm">
              <div className="mb-6">
                <h3 className="text-base font-semibold text-white">{t.connected_departments}</h3>
                <p className="text-xs text-zinc-400 mt-1">{t.shop_factories_labour}</p>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={240}>
                  <BarChart data={stats.charts.sources} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal vertical={false} stroke="#3f3f46" />
                    <XAxis type="number" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis dataKey="name" type="category" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} width={100} />
                    <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', color: '#f4f4f5' }} itemStyle={{ color: '#f4f4f5' }} cursor={{ fill: '#27272a' }} />
                    <Bar dataKey="records" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6 shadow-sm">
              <h3 className="text-base font-semibold text-white mb-6">{t.businesses_by_type}</h3>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={240}>
                  <PieChart>
                    <Pie data={stats.charts.sectors} cx="50%" cy="50%" innerRadius={80} outerRadius={110} stroke="none" paddingAngle={5} dataKey="value">
                      {stats.charts.sectors.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', color: '#f4f4f5' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <ListPanel title={t.business_status} subtitle={t.current_status_evidence} items={stats.charts.activity} total={stats.metrics.total_ubids} />
            <HotspotPanel items={stats.charts.pincode_hotspots} t={t} />
            <SimplePanel title={t.match_confidence} subtitle={t.strongly_match} items={stats.charts.confidence_bands} suffix={t.matches} t={t} />
          </div>

          <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-sm">
            <div className="px-6 py-5 border-b border-zinc-800">
              <h3 className="text-base font-semibold text-white">{t.ask_the_data}</h3>
              <p className="text-sm text-zinc-400 mt-1">{t.plain_english_questions}</p>
            </div>
            <div className="divide-y divide-zinc-800/50">
              {queryCards.map(card => {
                const run = queryRuns[card.question];
                const count = run?.data?.row_count ?? card.metric;
                const color = card.tone === 'warning' ? 'text-amber-400' : card.tone === 'review' ? 'text-rose-400' : 'text-primary';

                return (
                  <div key={card.question} className="px-6 py-4 hover:bg-zinc-900/50 transition-colors">
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                      <div>
                        <h4 className="text-sm font-medium text-white mb-1">"{card.label}"</h4>
                        <p className="text-xs text-zinc-500">{t.data_used}: {card.source} - {t.status}: {run?.data?.version_tag ? t.answered : t.ready}</p>
                        {run?.data?.summary_report && <p className="text-xs text-zinc-400 mt-2 max-w-4xl">{run.data.summary_report}</p>}
                        {run?.error && <p className="text-xs text-rose-400 mt-2">{run.error}</p>}
                      </div>
                      <div className="flex items-center justify-between lg:justify-end gap-4 w-full lg:w-auto lg:min-w-[320px]">
                        <div className="text-right">
                          <span className={`text-lg font-bold ${color}`}>{Number(count || 0).toLocaleString()}</span>
                          <span className="text-sm text-zinc-400 ml-2">{card.unit}</span>
                        </div>
                        <button onClick={() => runDashboardQuery(card)} disabled={run?.loading} className="w-9 h-9 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-200 hover:border-primary hover:text-white flex items-center justify-center" title={t.get_answer}>
                          {run?.loading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> : <PlayIcon size={16} />}
                        </button>
                        <button onClick={() => openQueryEngine(card.question)} className="w-9 h-9 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-200 hover:border-primary hover:text-white flex items-center justify-center" title={t.open_in_query}>
                          <ArrowRight01Icon size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'Geospatial' && (
        <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden min-h-[500px] animate-in fade-in flex flex-col">
          <div className="p-4 border-b border-zinc-800 bg-zinc-900/50 flex justify-between items-center">
            <div>
              <h2 className="text-lg font-bold text-white">{t.map_view}</h2>
              <p className="text-xs text-zinc-400">{t.showing_businesses.replace('{count}', mapData.length)}</p>
            </div>
            <div className="flex items-center gap-2 text-[10px] text-emerald-400 bg-emerald-500/10 px-3 py-1 rounded-full">
              <MapPinIcon size={12} />
              <span>{t.state_wide_map}</span>
            </div>
          </div>
          <div className="flex-1 relative z-0">
            <MapContainer center={[14.5, 75.7]} zoom={7} style={{ height: 'calc(100vh - 280px)', width: '100%' }}>
              <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              {mapData.map(point => (
                <Marker key={point.id} position={[point.lat, point.lng]} icon={getDataIcon(point.status)}>
                  <Popup className="custom-map-popup">
                    <div className="popup-container">
                      <div className="status-badge" style={{
                        backgroundColor: point.status === 'Active' ? '#064e3b' : point.status === 'Dormant' ? '#422006' : '#7f1d1d',
                        color: point.status === 'Active' ? '#10b981' : point.status === 'Dormant' ? '#f59e0b' : '#ef4444',
                        border: `1px solid ${point.status === 'Active' ? '#059669' : point.status === 'Dormant' ? '#eab308' : '#b91c1c'}`
                      }}>
                        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: point.status === 'Active' ? '#10b981' : point.status === 'Dormant' ? '#f59e0b' : '#ef4444' }}></div>
                        {point.status}
                      </div>
                      <p className="popup-title">{point.name}</p>
                      <p className="popup-ubid">{point.id}</p>
                      <button onClick={() => navigate(`/activity-status?ubid=${point.id}`)} className="popup-btn">{t.view_business_status}</button>
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
        </div>
      )}

      {activeTab === 'Sectors' && (
        <div className="space-y-6 animate-in fade-in">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
            <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-6">
              <div>
                <h2 className="text-xl font-bold text-white">{t.business_types}</h2>
                <p className="text-sm text-zinc-400 mt-1">{t.registered_by_type}</p>
              </div>
              <button
                onClick={() => openQueryEngine('Which business types have the most active, dormant, and closed businesses?')}
                className="flex items-center justify-center gap-2 px-4 py-2 bg-zinc-900 border border-zinc-800 hover:border-primary text-zinc-200 rounded-md text-sm"
              >
                {t.ask_about_types} <ArrowRight01Icon size={16} />
              </button>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              {stats.charts.sectors.map((sector, idx) => (
                <SectorPanel
                  key={sector.name}
                  sector={sector}
                  total={stats.metrics.total_ubids}
                  color={COLORS[idx % COLORS.length]}
                  icon={idx === 0 ? <Building02Icon size={22} /> : idx === 1 ? <Briefcase01Icon size={22} /> : idx === 2 ? <Database01Icon size={22} /> : <Activity01Icon size={22} />}
                  onOpen={() => openQueryEngine(`Show ${sector.name} businesses by status and PIN code`)}
                />
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <SimplePanel title={t.pin_code_hotspots} subtitle={t.areas_most_registered} items={stats.charts.pincode_hotspots} suffix={t.businesses} t={t} />
            <ListPanel title={t.business_status} subtitle={t.current_status_evidence} items={stats.charts.activity} total={stats.metrics.total_ubids} />
            <SimplePanel title={t.match_confidence} subtitle={t.strongly_match} items={stats.charts.confidence_bands} suffix={t.records} t={t} />
          </div>
        </div>
      )}
    </div>
  );
};

const MetricCard = ({ title, value, note, icon, tone = 'neutral' }) => {
  const toneClass = tone === 'primary' ? 'bg-primary/20 text-primary' : tone === 'success' ? 'bg-emerald-500/20 text-emerald-400' : tone === 'warning' ? 'bg-accent/20 text-accent' : 'bg-zinc-800/50 text-zinc-400';
  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 shadow-sm min-w-0">
      <div className="flex justify-between items-start mb-4">
        <div>
          <p className="text-zinc-400 text-sm font-medium mb-1">{title}</p>
          <h3 className="text-3xl font-bold text-white">{Number(value || 0).toLocaleString()}</h3>
        </div>
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${toneClass}`}>{icon}</div>
      </div>
      <p className="text-[11px] text-zinc-500">{note}</p>
    </div>
  );
};

const MiniMetric = ({ title, value, note }) => (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 min-w-0">
    <p className="text-zinc-400 text-sm font-medium mb-1">{title}</p>
    <h3 className="text-2xl font-bold text-white">{typeof value === 'number' ? value.toLocaleString() : value}</h3>
    <p className="text-[11px] text-zinc-500 mt-2">{note}</p>
  </div>
);

const ListPanel = ({ title, subtitle, items, total }) => (
  <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
    <h3 className="text-base font-semibold text-white mb-1">{title}</h3>
    <p className="text-xs text-zinc-400 mb-5">{subtitle}</p>
    <div className="space-y-3">
      {items.map(item => {
        const color = item.name === 'Active' ? 'bg-emerald-500' : item.name === 'Dormant' ? 'bg-amber-500' : 'bg-rose-500';
        return (
          <div key={item.name}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-zinc-300">{item.name}</span>
              <span className="text-zinc-500">{item.value.toLocaleString()}</span>
            </div>
            <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
              <div className={`h-full ${color}`} style={{ width: `${Math.min(100, (item.value / Math.max(total, 1)) * 100)}%` }}></div>
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

const HotspotPanel = ({ items, t }) => (
  <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
    <h3 className="text-base font-semibold text-white mb-1">{t?.pin_code_hotspots || 'PIN Code Hotspots'}</h3>
    <p className="text-xs text-zinc-400 mb-5">{t?.areas_most_registered || 'Areas with the most registered businesses'}</p>
    <div className="space-y-3">
      {items.slice(0, 6).map(item => (
        <div key={item.name} className="flex items-center justify-between text-sm">
          <span className="text-zinc-300 font-mono">{item.name}</span>
          <span className="text-zinc-500">{Number(item.active || 0).toLocaleString()} {t?.active2 || 'active'} / {Number(item.value || 0).toLocaleString()} {t?.total2 || 'total'}</span>
        </div>
      ))}
    </div>
  </div>
);

const SimplePanel = ({ title, subtitle, items, suffix, t }) => (
  <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
    <h3 className="text-base font-semibold text-white mb-1">{title}</h3>
    <p className="text-xs text-zinc-400 mb-5">{subtitle}</p>
    <div className="space-y-3">
      {items.map(item => (
        <div key={item.name} className="flex items-center justify-between text-sm">
          <span className="text-zinc-300">{item.name}</span>
          <span className="text-zinc-500">{Number(item.value || 0).toLocaleString()} {suffix}</span>
        </div>
      ))}
    </div>
  </div>
);

const SectorPanel = ({ sector, total, color, icon, onOpen }) => {
  const pct = Math.min(100, (Number(sector.value || 0) / Math.max(Number(total || 1), 1)) * 100);
  const active = Number(sector.active || 0);
  const dormant = Number(sector.dormant || 0);
  const closed = Number(sector.closed || 0);
  const statusTotal = Math.max(active + dormant + closed, 1);
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}22`, color }}>
            {icon}
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">{sector.name}</h3>
            <p className="text-xs text-zinc-500">{Number(sector.value || 0).toLocaleString()} businesses across {Number(sector.pin_count || 0).toLocaleString()} PIN codes</p>
          </div>
        </div>
        <button onClick={onOpen} className="text-xs text-primary hover:text-primary/80">Explore</button>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3">
        <MiniStat label="Active" value={active} tone="text-emerald-300" />
        <MiniStat label="Dormant" value={dormant} tone="text-amber-300" />
        <MiniStat label="Closed" value={closed} tone="text-rose-300" />
      </div>

      <div className="mt-5">
        <div className="flex justify-between text-xs text-zinc-500 mb-1">
          <span>Share of registry</span>
          <span>{pct.toFixed(1)}%</span>
        </div>
        <div className="h-2 bg-zinc-950 rounded-full overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }}></div>
        </div>
      </div>

      <div className="mt-4 h-2 bg-zinc-950 rounded-full overflow-hidden flex">
        <div className="bg-emerald-500" style={{ width: `${(active / statusTotal) * 100}%` }}></div>
        <div className="bg-amber-500" style={{ width: `${(dormant / statusTotal) * 100}%` }}></div>
        <div className="bg-rose-500" style={{ width: `${(closed / statusTotal) * 100}%` }}></div>
      </div>

      <div className="mt-4 flex items-center justify-between text-xs text-zinc-500">
        <span>{Number(sector.linked_records || 0).toLocaleString()} linked department records</span>
        <span>{Math.round(Number(sector.avg_confidence || 0) * 100)}% avg match</span>
      </div>
    </div>
  );
};

const MiniStat = ({ label, value, tone }) => (
  <div className="bg-zinc-950 border border-zinc-800 rounded-md p-3">
    <p className="text-[10px] text-zinc-500 uppercase tracking-wider">{label}</p>
    <p className={`text-lg font-bold ${tone}`}>{Number(value || 0).toLocaleString()}</p>
  </div>
);

export default Dashboard;
