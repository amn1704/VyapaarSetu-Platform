import { Link } from 'react-router-dom';
import { ArrowRight01Icon } from 'hugeicons-react/icons/ArrowRight01Icon';
import { Database01Icon } from 'hugeicons-react/icons/Database01Icon';
import { FingerPrintIcon } from 'hugeicons-react/icons/FingerPrintIcon';
import { CpuIcon } from 'hugeicons-react/icons/CpuIcon';
import { AiLockIcon } from 'hugeicons-react/icons/AiLockIcon';
import { Building02Icon } from 'hugeicons-react/icons/Building02Icon';
import { FileSearchIcon } from 'hugeicons-react/icons/FileSearchIcon';
import { TransactionHistoryIcon } from 'hugeicons-react/icons/TransactionHistoryIcon';
import { CheckmarkCircle01Icon } from 'hugeicons-react/icons/CheckmarkCircle01Icon';
import { Alert02Icon } from 'hugeicons-react/icons/Alert02Icon';
import { MapPinIcon } from 'hugeicons-react/icons/MapPinIcon';

import './LandingPage.css';
import { translations } from '../utils/translations';

const metrics = [
  ['3,111', 'source records'],
  ['1,001', 'canonical business IDs'],
  ['6', 'linked departments'],
  ['42', 'pending reviews']
];

const workflows = [
  {
    icon: <Database01Icon size={22} />,
    title: 'Unify source records',
    body: 'Normalize municipal, tax, utility, labour, and pollution-board records into one business graph.'
  },
  {
    icon: <FingerPrintIcon size={22} />,
    title: 'Resolve identity',
    body: 'Anchor links with PAN/GSTIN evidence, name similarity, location, and reviewer-safe confidence scores.'
  },
  {
    icon: <TransactionHistoryIcon size={22} />,
    title: 'Track lifecycle',
    body: 'Inspect activity status, linked records, audit history, and source evidence for any business ID.'
  },
  {
    icon: <FileSearchIcon size={22} />,
    title: 'Ask governed queries',
    body: 'Use local Llama text-to-SQL over read-only views that match the actual SQLite schema.'
  }
];

const pipeline = [
  ['01', 'One-way ingest', 'Read source records from department systems without modifying their schemas or workflows.'],
  ['02', 'Normalize evidence', 'Standardize names, addresses, pincode, PAN, GSTIN and sector hints for comparison.'],
  ['03', 'Score candidate pairs', 'Use anchors, fuzzy similarity, pincode and address overlap to produce explainable confidence.'],
  ['04', 'Govern the decision', 'Auto-link high confidence, route ambiguity to review, and keep low-confidence records separate.'],
  ['05', 'Classify activity', 'Use filings, renewals, inspections and consumption signals to infer Active, Dormant or Closed.']
];

const queryExamples = [
  'Active factories in pin 560058 with no inspection in the last 18 months',
  'PAN anchored businesses missing GSTIN capture',
  'Dormant entities showing recent department activity',
  'Ambiguous matches awaiting reviewer decision'
];

const safeguards = [
  'No source-system migration',
  'Reversible business ID linkages',
  'Explainable confidence signal',
  'Reviewer feedback loop',
  'Scrambled/synthetic sandbox data',
  'No hosted LLM calls on raw PII'
];

const LandingPage = ({ lang }) => {
  const t = translations[lang || 'en'];

  return (
    <div className="landing-shell">
      <section className="landing-hero">
        <header className="landing-header">
          <div className="landing-brand">
            <img src="/images/karnataka_gov_logo.png" alt="Government of Karnataka" />
            <div>
              <div className="landing-brand-title">VyapaarSetu</div>
              <div className="landing-brand-subtitle">{t.dept_name}</div>
            </div>
          </div>
          <div className="landing-header-tags">
            <span>{t.landing_tag_sqlite}</span>
            <span>{t.landing_tag_llm}</span>
          </div>
        </header>

        <div className="landing-hero-grid">
          <div className="landing-hero-copy">
            <div className="landing-kicker">{t.landing_kicker}</div>
            <h1>{t.landing_title}</h1>
            <p>
              {t.landing_subtitle}
            </p>
            <div className="landing-actions">
              <Link to="/dashboard" className="landing-primary">
                {t.landing_open_platform} <ArrowRight01Icon size={18} />
              </Link>
              <Link to="/query-engine" className="landing-secondary">
                {t.landing_run_query}
              </Link>
            </div>
          </div>

          <div className="landing-console" aria-label="Platform status preview">
            <div className="landing-console-bar">
              <span></span>
              <span></span>
              <span></span>
              <strong>live system snapshot</strong>
            </div>
            <div className="landing-metrics">
              {metrics.map(([value, label]) => (
                <div key={label} className="landing-metric">
                  <strong>{value}</strong>
                  <span>{label}</span>
                </div>
              ))}
            </div>
            <div className="landing-sql-card">
              <div className="landing-label">read-only query model</div>
              <code>
                SELECT ubid, business_name, status<br />
                FROM ubid_registry<br />
                WHERE pin_code = '560058';
              </code>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-section">
        <div className="landing-section-head">
          <span>Operational Workflows</span>
          <h2>Everything starts from the business identity graph.</h2>
        </div>
        <div className="landing-workflow-grid">
          {workflows.map((item) => (
            <article key={item.title} className="landing-workflow-card">
              <div className="landing-icon">{item.icon}</div>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section landing-two-column">
        <div>
          <span className="landing-section-tag">Local AI Boundary</span>
          <h2>Model-aware SQL without sending data outside the machine.</h2>
          <p>
            The local model is guided by read-only database views that mirror the
            actual SQLite data. Deterministic templates handle high-value civic
            query patterns, while SQL validation blocks unsafe statements.
          </p>
          <div className="landing-checks">
            {['Read-only views', 'Mutation blocker', 'Schema-aligned prompt', 'Factual result reports'].map(item => (
              <div key={item}><CheckmarkCircle01Icon size={16} /> {item}</div>
            ))}
          </div>
        </div>
        <div className="landing-stack">
          <div><Database01Icon size={20} /> SQLite / PostgreSQL-ready storage</div>
          <div><CpuIcon size={20} /> FastAPI async service layer</div>
          <div><AiLockIcon size={20} /> Local Ollama inference</div>
          <div><Building02Icon size={20} /> React admin workspace</div>
        </div>
      </section>

      <section className="landing-section landing-pipeline-section">
        <div className="landing-section-head">
          <span>Business ID Resolution Pipeline</span>
          <h2>From fragmented department rows to a governed business identity.</h2>
        </div>
        <div className="landing-pipeline">
          {pipeline.map(([step, title, body]) => (
            <article key={step} className="landing-pipeline-card">
              <strong>{step}</strong>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section landing-intel-grid">
        <div className="landing-query-panel">
          <span className="landing-section-tag">Active Business Intelligence</span>
          <h2>Questions Karnataka Commerce & Industry could not answer before business ID unification.</h2>
          <div className="landing-query-list">
            {queryExamples.map(item => (
              <div key={item}>
                <FileSearchIcon size={18} />
                <span>{item}</span>
              </div>
            ))}
          </div>
          <Link to="/query-engine" className="landing-primary">
            Open Query Engine <ArrowRight01Icon size={18} />
          </Link>
        </div>

        <div className="landing-review-panel">
          <div className="landing-review-head">
            <Alert02Icon size={22} />
            <div>
              <h3>Human-in-the-loop review</h3>
              <p>Wrong merges are costlier than missed matches.</p>
            </div>
          </div>
          <div className="landing-review-flow">
            <div><strong>Auto-link</strong><span>High confidence, strong identifier evidence</span></div>
            <div><strong>Review</strong><span>Ambiguous name/address or partial anchor evidence</span></div>
            <div><strong>Keep separate</strong><span>Low confidence or conflicting PAN/GSTIN</span></div>
          </div>
        </div>
      </section>

      <section className="landing-section landing-map-band">
        <div>
          <span className="landing-section-tag">State Coverage</span>
          <h2>Designed for Bengaluru Urban samples and expandable to Karnataka scale.</h2>
          <p>
            The current sandbox works with deterministic local data, but the architecture is built to sit beside 40+
            department systems across districts, pincode clusters and industrial areas.
          </p>
        </div>
        <div className="landing-district-grid">
          {['560058', '560001', '563101', '570001', '573201', '572101'].map(pin => (
            <div key={pin}><MapPinIcon size={15} /> {pin}</div>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <div className="landing-section-head">
          <span>Non-Negotiables Built In</span>
          <h2>Precision-first governance for public-sector business data.</h2>
        </div>
        <div className="landing-safeguards">
          {safeguards.map(item => (
            <div key={item}><CheckmarkCircle01Icon size={17} /> {item}</div>
          ))}
        </div>
      </section>

      <footer className="landing-footer">
        <div>
          <strong>{t.karnataka_ci}</strong>
          <span>VyapaarSetu project workspace</span>
        </div>
        <Link to="/activity-status" className="landing-secondary">
          Inspect activity status
        </Link>
      </footer>
    </div>
  );
};

export default LandingPage;
